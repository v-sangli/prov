"""prov ingest, annotate.

    prov ingest <format> <path> [--source-map F.jsonl] [--calib calib_ID ...] [--meta k=v] [--copy]
        Publish a recording folder (format: lerobot) as a session and register one ep_ ID per episode.

    prov annotate <ep_id> key=value [key=value ...]
        Label an episode (outcome, failure_type, tags, note, ...); the latest value wins.
"""

from pathlib import Path

from prov.cli.common import pairs
from prov.core.errors import ConfigError
from prov.episodes.annotate import annotate
from prov.episodes.ingest import ingest


def cmd_ingest(args, get_ctx) -> int:
    session, eps = ingest(get_ctx(), Path(args.path), format=args.format,
                          source_map=Path(args.source_map) if args.source_map else None,
                          calibrations=args.calib, meta=pairs(args.meta), copy=args.copy)
    print(f"{session.id}\t{len(eps)} episodes")
    return 0


def cmd_annotate(args, get_ctx) -> int:
    if not args.labels:
        raise ConfigError("give at least one key=value")
    annotate(get_ctx(), args.episode, pairs(args.labels))
    return 0


def register(sub, ext) -> None:
    ing = sub.add_parser("ingest", help="register a recording session and its episodes")
    ing.add_argument("format", choices=sorted(ext.formats))
    ing.add_argument("path")
    ing.add_argument("--source-map", help="JSONL: episode_index -> MCAP path/raw ID/time range")
    ing.add_argument("--calib", action="append", default=[], metavar="CALIB_ID")
    ing.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE")
    ing.add_argument("--copy", action="store_true", help="copy instead of move")
    ing.set_defaults(func=cmd_ingest)
    ann = sub.add_parser("annotate", help="label an episode")
    ann.add_argument("episode")
    ann.add_argument("labels", nargs="*", metavar="KEY=VALUE")
    ann.set_defaults(func=cmd_annotate)
