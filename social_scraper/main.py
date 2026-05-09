"""
main.py — Social Scraper Pipeline Runner

Usage:
  python main.py --agent all                  # Run full Scout → Harvester → Cleaner pipeline
  python main.py --agent scout                # Scout only
  python main.py --agent harvester            # Harvester only (uses latest scout output)
  python main.py --agent cleaner              # Cleaner only (uses latest harvested data)
  python main.py --agent scout --watch        # Scout in watch mode (runs every 6h)
  python main.py --agent all --platforms youtube reddit twitter
  python main.py --agent cleaner --translate --lang en
"""

import argparse
import sys
import os
import time
from pathlib import Path

# Make sure the scraper package root is on sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.logger import get_logger

logger = get_logger("main")


def run_scout(platforms: list[str] | None = None, watch: bool = False) -> str | None:
    from agents.scout_agent import ScoutAgent
    agent = ScoutAgent()
    if watch:
        logger.info("Starting Scout in watch mode (interval from config)...")
        agent.watch()
        return None
    logger.info("Running Scout agent...")
    results = agent.run(platforms=platforms)
    logger.info(f"Scout complete — {len(results)} entries across "
                f"{len({r['platform'] for r in results})} platforms")
    return agent._last_combined_path if hasattr(agent, "_last_combined_path") else None


def run_harvester(scout_file: str | None = None, platforms: list[str] | None = None) -> None:
    from agents.harvester_agent import HarvesterAgent
    agent = HarvesterAgent()
    if platforms:
        agent._platform_filter = platforms
    logger.info("Running Harvester agent...")
    agent.run(scout_file=scout_file)
    logger.info("Harvester complete.")


def run_cleaner(
    platforms: list[str] | None = None,
    translate: bool = False,
    target_lang: str = "en",
) -> None:
    from agents.cleaner_agent import CleanerAgent
    agent = CleanerAgent()
    logger.info("Running Cleaner agent...")
    stats = agent.run(platforms=platforms, translate=translate, target_lang=target_lang)
    for platform, s in (stats or {}).items():
        logger.info(f"  {platform}: {s.get('cleaned',0)} cleaned, "
                    f"{s.get('spam',0)} spam, {s.get('duplicates',0)} duplicates")
    logger.info("Cleaner complete.")


def run_all(
    platforms: list[str] | None = None,
    translate: bool = False,
    target_lang: str = "en",
) -> None:
    logger.info("=== Starting full pipeline: Scout → Harvester → Cleaner ===")
    start = time.time()

    scout_file = run_scout(platforms=platforms)
    run_harvester(scout_file=scout_file, platforms=platforms)
    run_cleaner(platforms=platforms, translate=translate, target_lang=target_lang)

    elapsed = time.time() - start
    logger.info(f"=== Pipeline complete in {elapsed:.1f}s ===")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Social Scraper — multi-agent data collection pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent", "-a",
        choices=["scout", "harvester", "cleaner", "all"],
        default="all",
        help="Which agent to run (default: all)",
    )
    parser.add_argument(
        "--platforms", "-p",
        nargs="+",
        metavar="PLATFORM",
        help="Limit to specific platforms (e.g. youtube reddit twitter)",
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Run scout in continuous watch mode (uses interval from config.json)",
    )
    parser.add_argument(
        "--scout-file", "-s",
        metavar="PATH",
        help="Path to scout output file (for harvester); uses latest if omitted",
    )
    parser.add_argument(
        "--translate", "-t",
        action="store_true",
        help="Translate non-English content (cleaner only)",
    )
    parser.add_argument(
        "--lang", "-l",
        default="en",
        metavar="LANG",
        help="Target language for translation (default: en)",
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="List all configured platforms and exit",
    )

    args = parser.parse_args()

    if args.list_platforms:
        from utils.config_loader import get_platform_config
        platforms = get_platform_config()
        print("\nConfigured platforms:")
        for name, cfg in sorted(platforms.items()):
            status = "✓ enabled" if cfg.get("enabled") else "✗ disabled"
            priority = cfg.get("priority", "–")
            print(f"  {name:<20} {status}  priority={priority}")
        print()
        return

    # Validate watch flag
    if args.watch and args.agent not in ("scout", "all"):
        parser.error("--watch is only supported with --agent scout or --agent all")

    # Dispatch
    if args.agent == "scout":
        run_scout(platforms=args.platforms, watch=args.watch)

    elif args.agent == "harvester":
        run_harvester(scout_file=args.scout_file, platforms=args.platforms)

    elif args.agent == "cleaner":
        run_cleaner(
            platforms=args.platforms,
            translate=args.translate,
            target_lang=args.lang,
        )

    elif args.agent == "all":
        if args.watch:
            # Watch mode for full pipeline: scout watches, then run rest after each cycle
            from apscheduler.schedulers.blocking import BlockingScheduler
            from utils.config_loader import get_scraping_config
            interval_h = get_scraping_config().get("schedule", {}).get("scout_interval_hours", 6)

            logger.info(f"Starting full pipeline in watch mode (every {interval_h}h)...")

            def full_cycle():
                scout_file = run_scout(platforms=args.platforms)
                run_harvester(scout_file=scout_file, platforms=args.platforms)
                run_cleaner(
                    platforms=args.platforms,
                    translate=args.translate,
                    target_lang=args.lang,
                )

            # Run immediately on start
            full_cycle()

            scheduler = BlockingScheduler()
            scheduler.add_job(full_cycle, "interval", hours=interval_h)
            logger.info("Scheduler started. Press Ctrl+C to stop.")
            try:
                scheduler.start()
            except KeyboardInterrupt:
                logger.info("Pipeline stopped by user.")
        else:
            run_all(
                platforms=args.platforms,
                translate=args.translate,
                target_lang=args.lang,
            )


if __name__ == "__main__":
    main()
