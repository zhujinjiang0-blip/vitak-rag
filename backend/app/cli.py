from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import uvicorn

from app.config import PROJECT_ROOT, get_settings
from app.services.evaluation import EvaluationService
from app.services.external_triples import ExternalTripleImporter
from app.services.ingest import IngestionService
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
    evaluate.add_argument("--output", default=str(PROJECT_ROOT / "data/eval/report.json"))
    evaluate.add_argument("--questions", default=None)
    evaluate.set_defaults(handler=_evaluate)

    generate_eval = subparsers.add_parser(
        "generate-eval",
        help="generate the stratified evaluation question set",
    )
    generate_eval.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data/eval/questions.jsonl"),
    )
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
    snapshot = SnapshotManager(get_settings()).bootstrap()
    try:
        count = EvaluationService(get_settings(), snapshot).write_questions(
            Path(args.output)
        )
        _print({"output": args.output, "questions": count})
    finally:
        snapshot.close()
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    snapshot = SnapshotManager(get_settings()).bootstrap()
    try:
        service = EvaluationService(get_settings(), snapshot)
        questions = None
        if args.questions:
            from app.services.evaluation import EvaluationQuestion

            questions = [
                EvaluationQuestion(**json.loads(line))
                for line in Path(args.questions).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        report = service.run(questions)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _print(
            {
                "output": str(output),
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
