"""Persistent in-session operation summaries."""

import time


def build(title, successes, failures, elapsed):
    return {
        "title": title,
        "successes": list(successes),
        "failures": list(failures),
        "elapsed": max(0.0, float(elapsed)),
        "created": time.strftime("%H:%M:%S"),
    }


def summary(report):
    return "{} | {} succeeded, {} skipped/failed | {:.3f}s".format(
        report["title"],
        len(report["successes"]),
        len(report["failures"]),
        report["elapsed"],
    )


def lines(report):
    result = ["[{}] {}".format(report["created"], summary(report))]
    result.extend("OK  " + item for item in report["successes"])
    result.extend("ERR " + item for item in report["failures"])
    return result
