import argparse
import json

from src.instagram_langgraph_agent import run_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangGraph Instagram HITL Agent")
    parser.add_argument(
        "--channel",
        default="email",
        choices=["email", "whatsapp"],
        help="Where to send HITL approval request.",
    )
    parser.add_argument(
        "--approve",
        default=None,
        choices=["yes", "no"],
        help="Simulate human approval decision in CLI demo.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    approved = None
    if args.approve is not None:
        approved = args.approve == "yes"

    result = run_agent(approval_channel=args.channel, human_approved=approved)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
