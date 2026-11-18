import argparse
import json
from os import path
from pathlib import Path
from genie.testbed import load
from genie.utils.diff import Diff
from pyats.async_ import pcall

FEATURES = ["ospf", "bgp", "interface", "routing"]


def learn_device_state(device):
    device.connect(stdout=False, log_stdout=False)
    snapshot = {}

    for feature in FEATURES:
        learned = device.learn(feature)
        snapshot[feature] = learned.to_dict() if hasattr(learned, "to_dict") else {}

    device.disconnect()
    return device.name, snapshot


def save_snapshot(testbed_file: str, output_file: str):
    testbed = load(path.join(path.dirname(__file__), testbed_file))
    devices = list(testbed.devices.values())

    print(f"Collecting snapshots from {len(devices)} devices in parallel...")
    results = pcall(learn_device_state, device=devices)
    full_snapshot = dict(results)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(full_snapshot, f, indent=2)

    print(f"[OK] Snapshot saved to {output_file}")


def compare_snapshots(pre_file: str, post_file: str, report_file: str | None = None):
    with open(pre_file) as f:
        pre_data = json.load(f)
    with open(post_file) as f:
        post_data = json.load(f)

    report_lines = []
    ignore_list = [
        r"(?i).*pkts.*",
        r"(?i).*octets.*",
        r"(?i).*rate.*",
        r"(?i).*timer.*",
        r"(?i).*errors.*",
        'age',
        'updated',
        'chars_in',
        'chars_out',
        'accounting'
    ]

    for hostname in pre_data:
        header = f"\n================ {hostname} ================"
        print(header)
        report_lines.append(header)

        diff = Diff(pre_data[hostname], post_data.get(hostname, {}), exclude=ignore_list)
        diff.findDiff()

        result = str(diff) if str(diff) else "No operational state changes detected."
        print(result)
        report_lines.append(result)

    if report_file:
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            f.write("\n".join(report_lines) + "\n")
        print(f"\n[OK] Diff report saved to {report_file}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automated Pre/Post Maintenance State Validator using pyATS/Genie"
    )
    subparsers = parser.add_subparsers(dest="stage", required=True)

    # Subcommand: pre
    pre_parser = subparsers.add_parser("pre", help="Capture pre-change network snapshot")
    pre_parser.add_argument("-t", "--testbed", default="testbed.yaml", help="Path to testbed YAML")
    pre_parser.add_argument("-o", "--output", default="snapshots/pre.json", help="Pre-change JSON path")

    # Subcommand: post
    post_parser = subparsers.add_parser("post", help="Capture post-change network snapshot")
    post_parser.add_argument("-t", "--testbed", default="testbed.yaml", help="Path to testbed YAML")
    post_parser.add_argument("-o", "--output", default="snapshots/post.json", help="Post-change JSON path")

    # Subcommand: diff
    diff_parser = subparsers.add_parser("diff", help="Compare pre and post snapshots")
    diff_parser.add_argument("--pre", default="snapshots/pre.json", help="Pre-change JSON path")
    diff_parser.add_argument("--post", default="snapshots/post.json", help="Post-change JSON path")
    diff_parser.add_argument("-r", "--report", default="snapshots/diff_report.txt", help="Save diff report to file")

    return parser.parse_args()


def main():
    args = parse_args()

    if args.stage == "pre":
        save_snapshot(args.testbed, args.output)
    elif args.stage == "post":
        save_snapshot(args.testbed, args.output)
    elif args.stage == "diff":
        compare_snapshots(args.pre, args.post, args.report)


if __name__ == "__main__":
    main()