from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

import uvicorn

from app.config import PROJECT_ROOT, get_settings
from app.schemas import UserRole
from app.services.auth import AuthStore
from app.services.evaluation import EvaluationService
from app.services.evidence_tables import EvidenceTableImporter, file_sha256
from app.services.external_triples import ExternalTripleImporter
from app.services.ingest import IngestionService
from app.services.runtime_llm import RuntimeLLMClient, RuntimeLLMError
from app.services.snapshot import DEMO_VERSION, SnapshotManager
from app.services.static_export import StaticExportService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vitak", description="VitaK-RAG utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="run the FastAPI server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true")

    subparsers.add_parser("seed-demo", help="create or open the demonstration snapshot")

    snapshot_list = subparsers.add_parser("snapshot-list", help="list snapshots")
    snapshot_list.set_defaults(handler=_snapshot_list)

    snapshot_validate = subparsers.add_parser(
        "snapshot-validate",
        help="validate a snapshot",
    )
    snapshot_validate.add_argument("version")
    snapshot_validate.set_defaults(handler=_snapshot_validate)

    snapshot_activate = subparsers.add_parser(
        "snapshot-activate",
        help="atomically activate a snapshot",
    )
    snapshot_activate.add_argument("version")
    snapshot_activate.set_defaults(handler=_snapshot_activate)

    snapshot_clone = subparsers.add_parser(
        "snapshot-clone",
        help="copy an existing snapshot to a new immutable version",
    )
    snapshot_clone.add_argument("base_version")
    snapshot_clone.add_argument("version")
    snapshot_clone.add_argument("--activate", action="store_true")
    snapshot_clone.set_defaults(handler=_snapshot_clone)

    auth_admin = subparsers.add_parser(
        "auth-init-admin",
        help="create the first research administrator",
    )
    auth_admin.add_argument("username")
    auth_admin.add_argument("password")
    auth_admin.add_argument("--display-name", default="")
    auth_admin.set_defaults(handler=_auth_init_admin)

    auth_user = subparsers.add_parser(
        "auth-create-user",
        help="create a researcher account",
    )
    auth_user.add_argument("username")
    auth_user.add_argument("password")
    auth_user.add_argument("--display-name", default="")
    auth_user.add_argument(
        "--role",
        choices=[UserRole.RESEARCHER.value, UserRole.ADMIN.value],
        default=UserRole.RESEARCHER.value,
    )
    auth_user.set_defaults(handler=_auth_create_user)

    for command, help_text in (
        ("auth-disable", "disable a research account"),
        ("auth-enable", "enable a research account"),
    ):
        status = subparsers.add_parser(command, help=help_text)
        status.add_argument("user")
        status.set_defaults(handler=_auth_change_status)

    auth_reset = subparsers.add_parser(
        "auth-reset-password",
        help="reset a password and revoke active sessions",
    )
    auth_reset.add_argument("user")
    auth_reset.add_argument("password")
    auth_reset.set_defaults(handler=_auth_reset_password)

    auth_revoke = subparsers.add_parser(
        "auth-revoke",
        help="revoke all sessions for an account",
    )
    auth_revoke.add_argument("user")
    auth_revoke.set_defaults(handler=_auth_revoke)

    subparsers.add_parser(
        "auth-list",
        help="list research accounts",
    ).set_defaults(handler=_auth_list)

    auth_audit = subparsers.add_parser(
        "auth-audit",
        help="show recent authentication and access audit records",
    )
    auth_audit.add_argument("--limit", type=int, default=100)
    auth_audit.set_defaults(handler=_auth_audit)

    llm_status = subparsers.add_parser(
        "runtime-llm-status",
        help="show runtime model configuration and optionally probe the endpoint",
    )
    llm_status.add_argument("--probe", action="store_true")
    llm_status.set_defaults(handler=_runtime_llm_status)

    ingest = subparsers.add_parser("ingest", help="import a document into a new snapshot")
    ingest.add_argument("path")
    ingest.add_argument("--title")
    ingest.add_argument("--source-type", default="document")
    ingest.add_argument(
        "--data-origin",
        choices=["internal", "external", "public", "synthetic"],
        default="internal",
    )
    ingest.add_argument("--data-owner", default="毕业设计内部资料")
    ingest.add_argument(
        "--access-scope",
        choices=["private", "controlled", "public"],
        default="private",
    )
    ingest.add_argument("--source-classification", default="")
    ingest.add_argument("--use-llm", action="store_true")
    ingest.add_argument("--activate", action="store_true")
    ingest.set_defaults(handler=_ingest)

    external_triples = subparsers.add_parser(
        "import-external-triples",
        help="import aligned_triples.csv from external vitamin K literature",
    )
    external_triples.add_argument("path")
    external_triples.add_argument("--data-owner", default="已发表维生素 K 研究文献")
    external_triples.add_argument("--activate", action="store_true")
    external_triples.set_defaults(handler=_import_external_triples)

    audit_evidence = subparsers.add_parser(
        "audit-evidence-tables",
        help="audit one or more unified 42-column evidence CSV files",
    )
    audit_evidence.add_argument("paths", nargs="+")
    audit_evidence.set_defaults(handler=_audit_evidence_tables)

    import_evidence = subparsers.add_parser(
        "import-evidence-tables",
        help="import one or more unified 42-column evidence CSV files",
    )
    import_evidence.add_argument("paths", nargs="+")
    import_evidence.add_argument("--version", default="vitak-real-2026.11")
    import_evidence.add_argument("--activate", action="store_true")
    import_evidence.add_argument("--limit-per-file", type=int, default=None)
    import_evidence.add_argument("--skip-vectors", action="store_true")
    import_evidence.add_argument(
        "--report",
        default=str(PROJECT_ROOT / "data/private_reports/vitak-real-2026.11-audit.json"),
    )
    import_evidence.set_defaults(handler=_import_evidence_tables)

    import_single = subparsers.add_parser(
        "import-evidence-table",
        help="import a single unified 42-column evidence CSV file",
    )
    import_single.add_argument("path")
    import_single.add_argument("--version", required=True)
    import_single.add_argument("--activate", action="store_true")
    import_single.add_argument("--limit", type=int, default=None)
    import_single.add_argument("--skip-vectors", action="store_true")
    import_single.set_defaults(handler=_import_evidence_table)

    review_export = subparsers.add_parser(
        "review-export",
        help="export pending extraction candidates as JSONL",
    )
    review_export.add_argument("--output", default=str(PROJECT_ROOT / "data/review/pending.jsonl"))
    review_export.set_defaults(handler=_review_export)

    review_apply = subparsers.add_parser(
        "review-apply",
        help="approve or reject pending extraction candidates",
    )
    review_apply.add_argument("--decision", choices=["approve", "reject"], required=True)
    review_apply.add_argument("--ids", nargs="*", default=[])
    review_apply.add_argument("--reviewer", default="local")
    review_apply.set_defaults(handler=_review_apply)

    rebuild = subparsers.add_parser(
        "rebuild-index",
        help="rebuild the active vector collection from SQLite chunks",
    )
    rebuild.set_defaults(handler=_rebuild_index)

    evaluate = subparsers.add_parser("evaluate", help="run the 80-question evaluation set")
    evaluate.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data/eval/report-two-group.json"),
    )
    evaluate.add_argument("--questions", default=None)
    evaluate.add_argument("--snapshot", default=None)
    evaluate.add_argument("--manifest-output", default=None)
    evaluate.set_defaults(handler=_evaluate)

    generate_eval = subparsers.add_parser(
        "generate-eval",
        help="generate the stratified evaluation question set",
    )
    generate_eval.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data/eval/questions.jsonl"),
    )
    generate_eval.add_argument("--snapshot", default=None)
    generate_eval.set_defaults(handler=_generate_eval)

    export_static = subparsers.add_parser(
        "export-static",
        help="export the active snapshot for the GitHub Pages demo",
    )
    export_static.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "frontend/public/demo-data.json"),
    )
    export_static.set_defaults(handler=_export_static)
    return parser


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _write_evaluation_artifacts(
    report: dict,
    output: Path,
    artifact_manifest: Path,
) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_sha256 = file_sha256(output)
    artifact_manifest.parent.mkdir(parents=True, exist_ok=True)
    artifact_manifest.write_text(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "report": {
                    "path": str(output.resolve()),
                    "sha256": report_sha256,
                },
                "inputs": report["inputs"],
                "reproducibility": report["reproducibility"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_sha256


def _snapshot_list(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    manager.bootstrap()
    _print(manager.list())
    return 0


def _snapshot_validate(args: argparse.Namespace) -> int:
    settings = get_settings()
    result = SnapshotManager(settings).validate(args.version)
    _print(result)
    return 0 if result["valid"] else 1


def _snapshot_activate(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    manager.bootstrap()
    _print(manager.activate(args.version))
    return 0


def _snapshot_clone(args: argparse.Namespace) -> int:
    settings = get_settings()
    context = SnapshotManager(settings).clone_snapshot(
        args.base_version,
        args.version,
        activate=args.activate,
    )
    try:
        _print(
            {
                "version": context.version,
                "path": str(context.root),
                "activated": args.activate,
                "manifest": context.manifest,
            }
        )
    finally:
        context.close()
    return 0


def _auth_store() -> AuthStore:
    settings = get_settings()
    return AuthStore(settings.resolved_auth_db_path, settings.session_ttl_hours)


def _auth_init_admin(args: argparse.Namespace) -> int:
    user = _auth_store().create_user(
        args.username,
        args.password,
        display_name=args.display_name,
        role=UserRole.ADMIN,
    )
    _print({"created": user.model_dump(mode="json"), "role": "admin"})
    return 0


def _auth_create_user(args: argparse.Namespace) -> int:
    user = _auth_store().create_user(
        args.username,
        args.password,
        display_name=args.display_name,
        role=UserRole(args.role),
    )
    _print({"created": user.model_dump(mode="json")})
    return 0


def _auth_change_status(args: argparse.Namespace) -> int:
    active = args.command == "auth-enable"
    changed = _auth_store().set_active(args.user, active)
    _print({"user": args.user, "active": active, "updated": changed})
    return 0 if changed else 1


def _auth_reset_password(args: argparse.Namespace) -> int:
    changed = _auth_store().reset_password(args.user, args.password)
    _print({"user": args.user, "password_reset": changed, "sessions_revoked": changed})
    return 0 if changed else 1


def _auth_revoke(args: argparse.Namespace) -> int:
    count = _auth_store().revoke_sessions(args.user)
    _print({"user": args.user, "sessions_revoked": count})
    return 0


def _auth_list(args: argparse.Namespace) -> int:
    _print([user.model_dump(mode="json") for user in _auth_store().list_users()])
    return 0


def _auth_audit(args: argparse.Namespace) -> int:
    _print(_auth_store().audit_log(args.limit))
    return 0


def _runtime_llm_status(args: argparse.Namespace) -> int:
    settings = get_settings()
    client = RuntimeLLMClient(settings)
    result = {
        "enabled": settings.runtime_llm_enabled,
        "configured": client.configured,
        "provider": client.provider,
        "model": client.model,
        "base_url_set": bool(settings.runtime_llm_base_url.strip()),
        "api_key_set": bool(settings.runtime_llm_api_key.strip()),
        "probe": "not_requested",
    }
    if args.probe and client.configured:
        try:
            client.parse_question(
                "维生素K是什么？",
                mode="domain",
                candidate_entities=[],
                filters={},
            )
            result["probe"] = "passed"
        except RuntimeLLMError as error:
            result["probe"] = "failed"
            result["error"] = str(error)
    _print(result)
    return 0 if result["probe"] != "failed" else 1


def _ingest(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    manager.bootstrap()
    result = IngestionService(settings, manager).ingest(
        Path(args.path),
        source_title=args.title,
        source_type=args.source_type,
        data_origin=args.data_origin,
        data_owner=args.data_owner,
        access_scope=args.access_scope,
        source_classification=args.source_classification,
        use_llm=args.use_llm,
        activate=args.activate,
    )
    _print(result)
    return 0


def _import_external_triples(args: argparse.Namespace) -> int:
    manager = SnapshotManager(get_settings())
    result = ExternalTripleImporter(manager).import_csv(
        Path(args.path),
        data_owner=args.data_owner,
        activate=args.activate,
    )
    _print(result)
    return 0


def _audit_evidence_tables(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    result = EvidenceTableImporter(manager).audit(Path(path) for path in args.paths)
    _print(result)
    return 0


def _import_evidence_tables(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    result = EvidenceTableImporter(manager).import_files(
        [Path(path) for path in args.paths],
        version=args.version,
        activate=args.activate,
        max_rows_per_file=args.limit_per_file,
        build_vectors=not args.skip_vectors,
        report_path=Path(args.report),
    )
    _print(result)
    return 0


def _import_evidence_table(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    result = EvidenceTableImporter(manager).import_files(
        [Path(args.path)],
        version=args.version,
        activate=args.activate,
        max_rows_per_file=args.limit,
        build_vectors=not args.skip_vectors,
    )
    _print(result)
    return 0


def _review_export(args: argparse.Namespace) -> int:
    snapshot = SnapshotManager(get_settings()).bootstrap()
    try:
        items = snapshot.metadata.list_review_items("pending")
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
            + ("\n" if items else ""),
            encoding="utf-8",
        )
        _print({"output": str(output), "count": len(items)})
    finally:
        snapshot.close()
    return 0


def _review_apply(args: argparse.Namespace) -> int:
    manager = SnapshotManager(get_settings())
    snapshot = manager.bootstrap()
    try:
        count = IngestionService(manager.settings, manager).apply_review(
            snapshot,
            args.ids,
            args.decision,
            args.reviewer,
        )
        _print({"updated": count, "decision": args.decision})
    finally:
        snapshot.close()
    return 0


def _rebuild_index(args: argparse.Namespace) -> int:
    snapshot = SnapshotManager(get_settings()).bootstrap()
    try:
        snapshot.vectors.reset()
        chunks = snapshot.metadata.all_chunks()
        for chunk in chunks:
            snapshot.vectors.upsert(
                chunk["id"],
                chunk["text"],
                {
                    "source_id": chunk["source_id"],
                    "is_demo": bool(chunk["is_demo"]),
                },
            )
        _print({"chunks": len(chunks), "vectors": snapshot.vectors.count()})
    finally:
        snapshot.close()
    return 0


def _generate_eval(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    snapshot = (
        manager.open(args.snapshot)
        if args.snapshot
        else manager.bootstrap()
    )
    try:
        count = EvaluationService(settings, snapshot).write_questions(
            Path(args.output)
        )
        _print({"output": args.output, "questions": count})
    finally:
        snapshot.close()
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    snapshot = (
        manager.open(args.snapshot)
        if args.snapshot
        else manager.bootstrap()
    )
    try:
        service = EvaluationService(settings, snapshot)
        questions = None
        question_path = Path(args.questions) if args.questions else None
        if question_path:
            from app.services.evaluation import EvaluationQuestion

            questions = [
                EvaluationQuestion(**json.loads(line))
                for line in question_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        report = service.run(questions)
        snapshot_manifest_path = snapshot.root / "manifest.json"
        code_root = Path(__file__).resolve().parent
        code_inputs = {
            path.relative_to(code_root).as_posix(): {
                "path": str(path),
                "sha256": file_sha256(path),
            }
            for path in (
                Path(__file__).resolve(),
                code_root / "services" / "evaluation.py",
                code_root / "services" / "qa.py",
                code_root / "services" / "qa_orchestrator.py",
            )
        }
        report["inputs"] = {
            "snapshot_manifest": {
                "path": str(snapshot_manifest_path),
                "sha256": file_sha256(snapshot_manifest_path),
            },
            "question_set": (
                {
                    "path": str(question_path.resolve()),
                    "sha256": file_sha256(question_path),
                }
                if question_path
                else {
                    "path": "generated_in_memory",
                    "sha256": "",
                }
            ),
            "code_files": code_inputs,
        }
        output = Path(args.output)
        artifact_manifest = (
            Path(args.manifest_output)
            if args.manifest_output
            else output.with_suffix(".manifest.json")
        )
        report["reproducibility"] = {
            "generation_command": shlex.join([sys.executable, *sys.argv]),
            "stable_ordering": {
                "question_order": "JSONL input order",
                "keyword": "bm25, evidence_id",
                "semantic": "vector score descending, evidence_id",
                "fusion": "reciprocal rank descending, evidence_id",
                "kg_keyword": "bm25, evidence_id during evaluation",
                "kg_phrase": "evidence_id during evaluation",
                "path_expectation_field": "expected_path_evidence_ids",
            },
            "python_hash_seed": os.environ.get("PYTHONHASHSEED", "unset"),
            "equivalence_exclusions": [
                "generated_at",
                "elapsed_ms",
                "summary.*.p95_ms",
            ],
            "self_hash": {
                "algorithm": "sha256",
                "location": str(artifact_manifest.resolve()),
            },
        }
        report_sha256 = _write_evaluation_artifacts(
            report,
            output,
            artifact_manifest,
        )
        _print(
            {
                "output": str(output),
                "manifest": str(artifact_manifest),
                "report_sha256": report_sha256,
                "question_count": report["question_count"],
                "summary": report["summary"],
            }
        )
    finally:
        snapshot.close()
    return 0


def _export_static(args: argparse.Namespace) -> int:
    snapshot = SnapshotManager(get_settings()).bootstrap()
    try:
        result = StaticExportService(snapshot).export(Path(args.output))
        _print(result)
    finally:
        snapshot.close()
    return 0


def _seed_demo(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = SnapshotManager(settings)
    manager.create_demo_snapshot()
    manager.activate(DEMO_VERSION)
    snapshot = manager.open(DEMO_VERSION)
    try:
        _print(snapshot.data_version.model_dump(mode="json"))
    finally:
        snapshot.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        settings = get_settings()
        uvicorn.run(
            "app.main:app",
            host=args.host or settings.host,
            port=args.port or settings.port,
            reload=args.reload,
        )
        return 0
    if args.command == "seed-demo":
        return _seed_demo(args)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
