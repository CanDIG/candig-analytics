"""
Generates a set of summary graphs from a per_program_completeness_report.csv file (the output of
run_completeness_reporting.py) and saves them as a single multi-page PDF.

Usage:
    python generate_completeness_graphs.py --input 2026-01-01_1200-UHN-per_program_completeness_report.csv
    python generate_completeness_graphs.py --input report.csv --output my_summary.pdf

If --output is not given, the PDF is named <input-file-stem>_summary_graphs.pdf.

Pages produced (any page whose required columns are missing from the input is skipped, with a
warning printed, so this also works against older report files that predate a given column set).
Every page carries a "Page N" footer.
    1. Cover page - node name, generation date, program/donor counts
    2. Node-wide completeness bucket distribution (minimal and fullsome side by side)
    3. Per-program completeness bucket distribution - minimal (100% stacked horizontal bar)
    4. Per-program completeness bucket distribution - fullsome (100% stacked horizontal bar)
    5. Average donor completeness per program (minimal vs fullsome, horizontal bar)
    6. Percentage of donors above 80% complete per program (minimal vs fullsome, horizontal bar)
    7. Tier-based completeness per program (existing tier_a/b/incomplete counts, minimal criteria)
    8. Tier-based completeness per program (existing tier_a/b/incomplete counts, fullsome criteria)

Per-program charts (3-8) use horizontal bars so program names never need to be rotated, and the
figure height scales with the number of programs (capped at a sane maximum) - this keeps the
charts readable whether a node has 3 programs or 100+.
"""
import argparse
import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

# Ordered from most-complete to least-complete, matching the half-open buckets in
# run_completeness_reporting.py's get_donor_pct_distribution (91-100%, 81-90%, ..., <=50%).
BUCKET_SUFFIXES = ['91_100_pct_complete', '81_90_pct_complete', '71_80_pct_complete',
                    '61_70_pct_complete', '51_60_pct_complete', 'under_50_pct_complete']
BUCKET_LABELS = ['91-100%', '81-90%', '71-80%', '61-70%', '51-60%', '<=50%']
# Perceptually-uniform, colour-blind-safe sequential scale (viridis) instead of a red/green
# diverging scale - brightest = most complete, darkest = least complete.
BUCKET_COLORS = [cm.viridis(x) for x in np.linspace(0.85, 0.10, len(BUCKET_SUFFIXES))]

# Colour-blind-safe (Okabe-Ito) palette used for the two-series and three-series comparison charts.
COLOR_MINIMAL = '#0072B2'    # blue
COLOR_FULLSOME = '#E69F00'   # orange
COLOR_TIER_A = '#009E73'     # bluish green
COLOR_TIER_B = '#0072B2'     # blue
COLOR_INCOMPLETE = '#D55E00'  # vermillion


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=str, required=True,
                        help="path to a per_program_completeness_report.csv file")
    parser.add_argument('--output', type=str, required=False, default=None,
                        help="path to the output PDF (default: <input-stem>_summary_graphs.pdf)")
    return parser.parse_args()


def _has_columns(df, columns):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        print(f"WARNING: skipping a page - missing column(s): {missing}")
        return False
    return True


def _bucket_columns(prefix):
    return [f'{prefix}_{suffix}' for suffix in BUCKET_SUFFIXES]


def _dynamic_figsize(n_items, base_width=9.0, per_item=0.35, min_height=5.0, max_height=40.0):
    """Scales figure height with the number of bars (programs) so charts stay readable whether a
    node has 3 programs or 100+. Height is capped so the PDF page doesn't get absurdly large -
    beyond ~110 programs the chart will feel cramped and may be worth splitting across pages."""
    height = min(max_height, max(min_height, n_items * per_item))
    return base_width, height


def _tick_fontsize(n_items):
    if n_items > 60:
        return 6
    if n_items > 30:
        return 8
    return 10


def _save_page(pdf, fig, page_counter):
    page_counter[0] += 1
    fig.text(0.99, 0.01, f"Page {page_counter[0]}", ha='right', va='bottom', fontsize=8, color='gray')
    pdf.savefig(fig)
    plt.close(fig)


def add_cover_page(pdf, df, input_path, page_counter):
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    node = df['node'].iloc[0] if 'node' in df.columns and len(df) else 'unknown'
    n_programs = df['program_id'].nunique() if 'program_id' in df.columns else len(df)
    total_donors = int(df['donor_count'].sum()) if 'donor_count' in df.columns else None
    lines = [
        "MOHCCN Completeness Report - Summary Graphs",
        "",
        f"Node: {node}",
        f"Source file: {Path(input_path).name}",
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Programs: {n_programs}",
    ]
    if total_donors is not None:
        lines.append(f"Total donors: {total_donors}")
    ax.text(0.05, 0.9, "\n".join(lines), va='top', ha='left', fontsize=14, transform=ax.transAxes)
    _save_page(pdf, fig, page_counter)


def add_node_wide_bucket_histogram(pdf, df, page_counter):
    minimal_cols = _bucket_columns('minimal')
    fullsome_cols = _bucket_columns('fullsome')
    have_minimal = _has_columns(df, minimal_cols)
    have_fullsome = _has_columns(df, fullsome_cols)
    if not have_minimal and not have_fullsome:
        return

    fig, axes = plt.subplots(1, 2, figsize=(11, 6))
    for ax, cols, title, have in [(axes[0], minimal_cols, "Minimal completeness (node-wide)", have_minimal),
                                  (axes[1], fullsome_cols, "Fullsome completeness (node-wide)", have_fullsome)]:
        if not have:
            ax.axis('off')
            continue
        totals = [int(df[c].sum()) for c in cols]
        bars = ax.bar(BUCKET_LABELS, totals, color=BUCKET_COLORS)
        ax.set_title(title)
        ax.set_ylabel("Number of donors")
        ax.set_xlabel("% Complete Frequency")
        ax.tick_params(axis='x', rotation=30)
        for bar, total in zip(bars, totals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), str(total),
                    ha='center', va='bottom', fontsize=9)
    fig.suptitle("Donor count by completeness bucket - all programs combined")
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def add_per_program_stacked_bucket_bar(pdf, df, prefix, title, page_counter):
    cols = _bucket_columns(prefix)
    if not _has_columns(df, cols) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    lefts = np.zeros(len(programs))
    for col, label, color in zip(cols, BUCKET_LABELS, BUCKET_COLORS):
        values = df[col].to_numpy(dtype=float)
        ax.barh(programs, values, left=lefts, label=label, color=color)
        lefts += values
    ax.set_title(title)
    ax.set_xlabel("Number of donors")
    ax.set_ylabel("Program")
    ax.tick_params(axis='y', labelsize=_tick_fontsize(len(programs)))
    ax.invert_yaxis()
    ax.legend(title="Completeness", bbox_to_anchor=(1.02, 1), loc='upper left')
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def add_avg_completeness_bar(pdf, df, page_counter):
    cols = ['minimal_avg_pct_complete', 'fullsome_avg_pct_complete']
    if not _has_columns(df, cols) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    y = np.arange(len(programs))
    height = 0.35
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    ax.barh(y - height / 2, df['minimal_avg_pct_complete'], height, label='Minimal', color=COLOR_MINIMAL)
    ax.barh(y + height / 2, df['fullsome_avg_pct_complete'], height, label='Fullsome', color=COLOR_FULLSOME)
    ax.set_yticks(y)
    ax.set_yticklabels(programs, fontsize=_tick_fontsize(len(programs)))
    ax.invert_yaxis()
    ax.set_xlabel("Average donor completeness (%)")
    ax.set_title("Average donor completeness per program")
    ax.set_xlim(0, 100)
    ax.legend()
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def add_pct_over_80_bar(pdf, df, page_counter):
    cols = ['minimal_pct_donors_over_80', 'fullsome_pct_donors_over_80']
    if not _has_columns(df, cols) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    y = np.arange(len(programs))
    height = 0.35
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    ax.barh(y - height / 2, df['minimal_pct_donors_over_80'], height, label='Minimal', color=COLOR_MINIMAL)
    ax.barh(y + height / 2, df['fullsome_pct_donors_over_80'], height, label='Fullsome', color=COLOR_FULLSOME)
    ax.set_yticks(y)
    ax.set_yticklabels(programs, fontsize=_tick_fontsize(len(programs)))
    ax.invert_yaxis()
    ax.set_xlabel("% of donors with completeness > 80%")
    ax.set_title("Donors above 80% complete, per program")
    ax.set_xlim(0, 100)
    ax.legend()
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def add_tier_breakdown_bar(pdf, df, tier_a_col, tier_b_col, incomplete_col, title, page_counter):
    cols = [tier_a_col, tier_b_col, incomplete_col]
    if not _has_columns(df, cols) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    lefts = np.zeros(len(programs))
    for col, label, color in zip(cols, ['Tier A', 'Tier B', 'Incomplete'],
                                 [COLOR_TIER_A, COLOR_TIER_B, COLOR_INCOMPLETE]):
        values = df[col].to_numpy(dtype=float)
        ax.barh(programs, values, left=lefts, label=label, color=color)
        lefts += values
    ax.set_title(title)
    ax.set_xlabel("Number of donors")
    ax.set_ylabel("Program")
    ax.tick_params(axis='y', labelsize=_tick_fontsize(len(programs)))
    ax.invert_yaxis()
    ax.legend()
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def main():
    args = parse_args()
    df = pd.read_csv(args.input)
    output_path = args.output or f"{Path(args.input).stem}_summary_graphs.pdf"
    page_counter = [0]

    with PdfPages(output_path) as pdf:
        add_cover_page(pdf, df, args.input, page_counter)
        add_node_wide_bucket_histogram(pdf, df, page_counter)
        add_per_program_stacked_bucket_bar(pdf, df, 'minimal',
                                           "Donors per program by minimal completeness", page_counter)
        add_per_program_stacked_bucket_bar(pdf, df, 'fullsome',
                                           "Donors per program by fullsome completeness", page_counter)
        add_avg_completeness_bar(pdf, df, page_counter)
        add_pct_over_80_bar(pdf, df, page_counter)
        add_tier_breakdown_bar(pdf, df, 'tier_a_min_cg_complete', 'tier_b_min_cg_complete',
                               'incomplete_min_donors', "Minimal clinical + genomic tier breakdown per program",
                               page_counter)
        add_tier_breakdown_bar(pdf, df, 'tier_a_full_cg_complete', 'tier_b_full_cg_complete',
                               'incomplete_full_donors', "Fullsome clinical + genomic tier breakdown per program",
                               page_counter)

    print(f"Saved summary graphs to '{output_path}' ({page_counter[0]} pages)")


if __name__ == "__main__":
    main()
