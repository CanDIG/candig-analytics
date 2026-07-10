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
    1. Cover page - node name, generation date, node-wide summary statistics table
    2. Node-wide completeness bucket distribution (minimal and fullsome side by side)
    3. Per-program completeness bucket distribution - minimal (stacked horizontal bar, raw counts)
    4. Per-program completeness bucket distribution - fullsome (stacked horizontal bar, raw counts)
    5. Per-program summary table - donor count, average completeness and >80%-complete count/
       percentage, both minimal and fullsome
    6. Tier-based completeness per program, minimal criteria (raw tier_a/b/incomplete counts)
    7. Tier-based completeness per program, minimal criteria (100% stacked bar)
    8. Tier-based completeness per program, fullsome criteria (raw tier_a/b/incomplete counts)
    9. Tier-based completeness per program, fullsome criteria (100% stacked bar)

Per-program charts (3-9) use horizontal bars so program names never need to be rotated, and the
figure height scales with the number of programs (capped at a sane maximum) - this keeps the
charts readable whether a node has 3 programs or 100+. Categorical (program) axis limits are set
tightly around the bars rather than relying on matplotlib's default 5% margin, to avoid large
empty gaps above the first and below the last program.
"""
import argparse
import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd

# Ordered from most-complete to least-complete, matching the half-open buckets in
# run_completeness_reporting.py's get_donor_pct_distribution (91-100%, 81-90%, ..., <=50%).
BUCKET_SUFFIXES = ['91_100_pct_complete', '81_90_pct_complete', '71_80_pct_complete',
                    '61_70_pct_complete', '51_60_pct_complete', 'under_50_pct_complete']
BUCKET_LABELS = ['91-100%', '81-90%', '71-80%', '61-70%', '51-60%', '<=50%']
# Colour-blind-safe qualitative palette (Okabe-Ito, https://jfly.uni-koeln.de/color/) - each bucket
# gets a clearly distinct hue rather than a sequential gradient, which was hard to tell apart
# between adjacent buckets.
BUCKET_COLORS = ['#009E73', '#56B4E9', '#F0E442', '#E69F00', '#CC79A7', '#D55E00']

# Colour-blind-safe (Okabe-Ito) palette used for the tier breakdown charts.
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


def _pct_of(count, total):
    if not total:
        return ''
    return f"{100 * count / total:.1f}%"


def _node_summary_rows(df, total_donors):
    """Builds the cover-page summary table rows, skipping any stat whose source columns are
    missing from the input (so this still works against older report files)."""
    rows = []
    if 'program_id' in df.columns:
        rows.append(["Total programs", str(df['program_id'].nunique()), ''])
    if total_donors is not None:
        rows.append(["Total donors", str(total_donors), ''])
    if _has_columns(df, ['tier_a_min_cg_complete', 'tier_b_min_cg_complete']):
        n = int(df['tier_a_min_cg_complete'].sum() + df['tier_b_min_cg_complete'].sum())
        rows.append(["Total minimal clinical + genomic complete", str(n), _pct_of(n, total_donors)])
    if _has_columns(df, ['minimal_91_100_pct_complete', 'minimal_81_90_pct_complete']):
        n = int(df['minimal_91_100_pct_complete'].sum() + df['minimal_81_90_pct_complete'].sum())
        rows.append(["Total >80% minimal clinical complete", str(n), _pct_of(n, total_donors)])
    if _has_columns(df, ['tier_a_full_cg_complete', 'tier_b_full_cg_complete']):
        n = int(df['tier_a_full_cg_complete'].sum() + df['tier_b_full_cg_complete'].sum())
        rows.append(["Total fullsome clinical + genomic complete", str(n), _pct_of(n, total_donors)])
    if _has_columns(df, ['fullsome_91_100_pct_complete', 'fullsome_81_90_pct_complete']):
        n = int(df['fullsome_91_100_pct_complete'].sum() + df['fullsome_81_90_pct_complete'].sum())
        rows.append(["Total >80% fullsome clinical complete", str(n), _pct_of(n, total_donors)])
    return rows


def add_cover_page(pdf, df, input_path, page_counter):
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    node = df['node'].iloc[0] if 'node' in df.columns and len(df) else 'unknown'
    total_donors = int(df['donor_count'].sum()) if 'donor_count' in df.columns else None
    header_lines = [
        "MOHCCN Completeness Report - Summary Graphs",
        "",
        f"Node: {node}",
        f"Source file: {Path(input_path).name}",
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    ax.text(0.05, 0.95, "\n".join(header_lines), va='top', ha='left', fontsize=14, transform=ax.transAxes)

    rows = _node_summary_rows(df, total_donors)
    if rows:
        col_widths = [0.62, 0.14, 0.24]
        table = ax.table(cellText=rows, colLabels=["Metric", "Count", "% of total donors"],
                         cellLoc='left', colLoc='left', colWidths=col_widths, bbox=[0.05, 0.35, 0.9, 0.4])
        table.auto_set_font_size(False)
        table.set_fontsize(10.5)
        for (row_idx, col_idx), cell in table.get_celld().items():
            cell.set_edgecolor('#CCCCCC')
            cell.PAD = 0.02
            if row_idx == 0:
                cell.set_facecolor('#EEEEEE')
                cell.set_text_props(fontweight='bold')
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
        # Tight bottom (bars start at exactly 0, no default-margin gap below them) with just
        # enough headroom on top for the count labels.
        ax.set_ylim(0, max(totals) * 1.15 if max(totals) > 0 else 1)
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
    y = np.arange(len(programs))
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    lefts = np.zeros(len(programs))
    for col, label, color in zip(cols, BUCKET_LABELS, BUCKET_COLORS):
        values = df[col].to_numpy(dtype=float)
        ax.barh(y, values, left=lefts, label=label, color=color)
        lefts += values
    ax.set_title(title)
    ax.set_xlabel("Number of donors")
    ax.set_ylabel("Program")
    ax.set_yticks(y)
    ax.set_yticklabels(programs, fontsize=_tick_fontsize(len(programs)))
    # Tight, inverted y-limits (first program at top, last at bottom) instead of the default 5%
    # categorical margin, which left large empty gaps above/below the bars.
    ax.set_ylim(len(programs) - 0.5, -0.5)
    ax.set_xlim(left=0)
    ax.legend(title="Completeness", bbox_to_anchor=(1.02, 1), loc='upper left')
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def _table_fontsize(n_items):
    if n_items > 60:
        return 5.5
    if n_items > 30:
        return 7
    return 9


def _text_color_for_bg(rgba):
    """Picks black or white text for readability against a given RGBA background, based on
    perceptual luminance."""
    r, g, b = rgba[0], rgba[1], rgba[2]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return 'white' if luminance < 0.5 else 'black'


def add_program_summary_table(pdf, df, page_counter):
    """
    Replaces the separate "average completeness" and ">80% complete" bar charts with a single
    table: one row per program, with both the raw donor count and the percentage for the >80%
    columns (not just the percentage) so each row is self-contained without needing to cross-
    reference donor_count elsewhere. The four percentage columns (avg completeness and >80%
    complete, minimal and fullsome) are additionally shaded using the magma colormap (0-100%, 80%
    opacity) so low/high performers are visible at a glance, with a colorbar legend alongside the
    table.
    """
    required = ['donor_count', 'minimal_avg_pct_complete', 'fullsome_avg_pct_complete',
                'minimal_pct_donors_over_80', 'fullsome_pct_donors_over_80',
                'minimal_91_100_pct_complete', 'minimal_81_90_pct_complete',
                'fullsome_91_100_pct_complete', 'fullsome_81_90_pct_complete']
    if not _has_columns(df, required) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    minimal_over80_counts = (df['minimal_91_100_pct_complete'] + df['minimal_81_90_pct_complete']).astype(int)
    fullsome_over80_counts = (df['fullsome_91_100_pct_complete'] + df['fullsome_81_90_pct_complete']).astype(int)

    rows = []
    for i in range(len(df)):
        rows.append([
            programs[i],
            str(int(df['donor_count'].iloc[i])),
            f"{df['minimal_avg_pct_complete'].iloc[i]:.1f}%",
            f"{df['fullsome_avg_pct_complete'].iloc[i]:.1f}%",
            f"{minimal_over80_counts.iloc[i]} ({df['minimal_pct_donors_over_80'].iloc[i]:.1f}%)",
            f"{fullsome_over80_counts.iloc[i]} ({df['fullsome_pct_donors_over_80'].iloc[i]:.1f}%)",
        ])

    col_labels = ["Program", "Donor\ncount", "Avg completeness\n(minimal)", "Avg completeness\n(fullsome)",
                  ">80% complete\n(minimal)", ">80% complete\n(fullsome)"]
    col_widths = [0.22, 0.12, 0.17, 0.17, 0.16, 0.16]

    # Column indices (1-based, matching table.get_celld() keys) whose cells get shaded by their
    # underlying percentage value, mapped to the values themselves.
    pct_by_col = {
        2: df['minimal_avg_pct_complete'].tolist(),
        3: df['fullsome_avg_pct_complete'].tolist(),
        4: df['minimal_pct_donors_over_80'].tolist(),
        5: df['fullsome_pct_donors_over_80'].tolist(),
    }
    cmap = plt.get_cmap('magma')
    norm = Normalize(vmin=0, vmax=100)
    cell_alpha = 0.8

    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs), per_item=0.32, min_height=3))
    # Pin the axes to fill almost the entire figure, in FIGURE (not axes-relative) coordinates.
    # matplotlib's default subplot margins reserve a fixed FRACTION of figure height for the title
    # area - fine on a normal-sized figure, but on the very tall figures used here for many
    # programs (up to 40in) that fraction turns into inches of blank space above the table. Setting
    # the position explicitly keeps the gap a fixed size regardless of how tall the figure gets.
    # Left a slice of figure width free (0.88-1.0) for the colorbar legend added below.
    ax.set_position([0.02, 0.01, 0.86, 0.97])
    ax.axis('off')
    ax.text(0.5, 0.99, "Per-program completeness summary", ha='center', va='top', fontsize=14,
           fontweight='bold', transform=ax.transAxes)
    table = ax.table(cellText=rows, colLabels=col_labels, cellLoc='center', colLoc='center',
                     colWidths=col_widths, bbox=[0.0, 0.0, 1.0, 0.94])
    table.auto_set_font_size(False)
    table.set_fontsize(_table_fontsize(len(programs)))
    for (row_idx, col_idx), cell in table.get_celld().items():
        cell.set_edgecolor('#CCCCCC')
        if row_idx == 0:
            cell.set_facecolor('#EEEEEE')
            cell.set_text_props(fontweight='bold')
        elif col_idx in pct_by_col:
            r, g, b, _ = cmap(norm(pct_by_col[col_idx][row_idx - 1]))
            cell.set_facecolor((r, g, b, cell_alpha))
            # Base the text-contrast decision on the opaque colour, not the 80%-alpha one, since
            # the cell is drawn over a white page background regardless of its own alpha.
            cell.set_text_props(color=_text_color_for_bg((r, g, b)))
        elif row_idx % 2 == 0:
            cell.set_facecolor('#F7F7F7')

    cbar_ax = fig.add_axes([0.90, 0.2, 0.02, 0.5])
    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.solids.set_alpha(cell_alpha)
    cbar.set_label('% complete', fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    _save_page(pdf, fig, page_counter)


def add_tier_breakdown_bar(pdf, df, tier_a_col, tier_b_col, incomplete_col, title, page_counter):
    cols = [tier_a_col, tier_b_col, incomplete_col]
    if not _has_columns(df, cols) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    y = np.arange(len(programs))
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    lefts = np.zeros(len(programs))
    for col, label, color in zip(cols, ['Tier A', 'Tier B', 'Incomplete'],
                                 [COLOR_TIER_A, COLOR_TIER_B, COLOR_INCOMPLETE]):
        values = df[col].to_numpy(dtype=float)
        ax.barh(y, values, left=lefts, label=label, color=color)
        lefts += values
    ax.set_title(title)
    ax.set_xlabel("Number of donors")
    ax.set_ylabel("Program")
    ax.set_yticks(y)
    ax.set_yticklabels(programs, fontsize=_tick_fontsize(len(programs)))
    ax.set_ylim(len(programs) - 0.5, -0.5)
    ax.set_xlim(left=0)
    ax.legend()
    fig.tight_layout()
    _save_page(pdf, fig, page_counter)


def add_tier_breakdown_pct_bar(pdf, df, tier_a_col, tier_b_col, incomplete_col, title, page_counter):
    """100%-stacked version of add_tier_breakdown_bar: each program's tier_a/b/incomplete counts
    expressed as a percentage of that program's donor_count, so programs of very different sizes
    can be compared directly on the same 0-100% scale."""
    cols = [tier_a_col, tier_b_col, incomplete_col, 'donor_count']
    if not _has_columns(df, cols) or 'program_id' not in df.columns:
        return
    programs = df['program_id'].tolist()
    y = np.arange(len(programs))
    donor_count = df['donor_count'].to_numpy(dtype=float)
    donor_count_safe = np.where(donor_count == 0, np.nan, donor_count)
    fig, ax = plt.subplots(figsize=_dynamic_figsize(len(programs)))
    lefts = np.zeros(len(programs))
    for col, label, color in zip([tier_a_col, tier_b_col, incomplete_col], ['Tier A', 'Tier B', 'Incomplete'],
                                 [COLOR_TIER_A, COLOR_TIER_B, COLOR_INCOMPLETE]):
        pct_values = 100 * df[col].to_numpy(dtype=float) / donor_count_safe
        pct_values = np.nan_to_num(pct_values)
        ax.barh(y, pct_values, left=lefts, label=label, color=color)
        lefts += pct_values
    ax.set_title(title)
    ax.set_xlabel("% of program's donors")
    ax.set_ylabel("Program")
    ax.set_yticks(y)
    ax.set_yticklabels(programs, fontsize=_tick_fontsize(len(programs)))
    ax.set_ylim(len(programs) - 0.5, -0.5)
    ax.set_xlim(0, 100)
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
        add_program_summary_table(pdf, df, page_counter)
        add_tier_breakdown_bar(pdf, df, 'tier_a_min_cg_complete', 'tier_b_min_cg_complete',
                               'incomplete_min_donors', "Minimal clinical + genomic tier breakdown per program",
                               page_counter)
        add_tier_breakdown_pct_bar(pdf, df, 'tier_a_min_cg_complete', 'tier_b_min_cg_complete',
                                   'incomplete_min_donors',
                                   "Minimal clinical + genomic tier breakdown per program (% of donors)",
                                   page_counter)
        add_tier_breakdown_bar(pdf, df, 'tier_a_full_cg_complete', 'tier_b_full_cg_complete',
                               'incomplete_full_donors', "Fullsome clinical + genomic tier breakdown per program",
                               page_counter)
        add_tier_breakdown_pct_bar(pdf, df, 'tier_a_full_cg_complete', 'tier_b_full_cg_complete',
                                   'incomplete_full_donors',
                                   "Fullsome clinical + genomic tier breakdown per program (% of donors)",
                                   page_counter)

    print(f"Saved summary graphs to '{output_path}' ({page_counter[0]} pages)")


if __name__ == "__main__":
    main()
