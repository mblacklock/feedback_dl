"""Matplotlib-based server-side SVG chart generation utilities."""
import io
import numpy as np
import matplotlib
# Use non-interactive Agg backend to avoid GUI threads/issues
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def generate_radar_chart(categories, student_percentages, average_percentages, pass_mark=40):
    """
    Generate a radar chart with a straight-sided (polygon) grid comparing a
    student's marks against the class average in percentage terms (0-100%).

    Uses a manual polygon-based approach so grid rings are diamond/square
    shaped rather than circular, matching the reference style.

    Args:
        categories: List of category label strings
        student_percentages: List of student percentages matching the categories
        average_percentages: List of class average percentages matching the categories
        pass_mark: Pass threshold percentage — drawn as a red dashed polygon ring.
                   Use 40 for UG, 50 for M-level. Defaults to 40.

    Returns:
        str: SVG XML string representing the vector chart
    """
    num_vars = len(categories)
    if num_vars == 0:
        return ""

    # Angles for each axis, starting from top (90 degrees) going clockwise
    angles = np.linspace(np.pi / 2, np.pi / 2 + 2 * np.pi, num_vars, endpoint=False)

    def polar_to_xy(r, theta):
        return r * np.cos(theta), r * np.sin(theta)

    def make_polygon(values, angles, scale=1.0):
        """Convert percentage values to (x, y) polygon points, normalised to scale."""
        xs, ys = [], []
        for v, a in zip(values, angles):
            r = (v / 100.0) * scale
            x, y = polar_to_xy(r, a)
            xs.append(x)
            ys.append(y)
        xs.append(xs[0])
        ys.append(ys[0])
        return xs, ys

    # Colours
    student_color = '#74c476'   # Green — matches histogram 1st colour
    average_color = '#7bafd4'   # Blue — matches histogram 2:2 colour
    grid_color    = '#cccccc'
    label_color   = '#1e293b'
    scale = 1.0  # unit circle radius

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.set_aspect('equal')
    ax.axis('off')

    # Draw polygon grid rings at 20, 40, 60, 80, 100%
    for level in [0.2, 0.4, 0.6, 0.8, 1.0]:
        ring_xs, ring_ys = make_polygon([level * 100] * num_vars, angles, scale)
        ax.plot(ring_xs, ring_ys, color=grid_color, linewidth=0.8, zorder=1)
        # Label the ring on the first axis
        label_x, label_y = polar_to_xy(level * scale, angles[0])
        ax.text(label_x, label_y, f'{int(level * 100)}',
                ha='center', va='bottom', fontsize=9, color='#888888')

    # Draw axis spokes
    for a in angles:
        x, y = polar_to_xy(scale, a)
        ax.plot([0, x], [0, y], color=grid_color, linewidth=0.8, zorder=1)

    # Draw pass mark threshold ring — red dashed polygon
    pass_xs, pass_ys = make_polygon([pass_mark] * num_vars, angles, scale)
    ax.plot(pass_xs, pass_ys, color='#d9534f', linewidth=1.5,
            linestyle='--', zorder=2, label=f'Pass Mark ({pass_mark}%)')

    # Draw class average polygon
    avg_xs, avg_ys = make_polygon(list(average_percentages), angles, scale)
    ax.fill(avg_xs, avg_ys, color=average_color, alpha=0.25, zorder=2)
    ax.plot(avg_xs, avg_ys, color=average_color, linewidth=2.0, zorder=3, label='Class Average')

    # Draw student polygon
    stu_xs, stu_ys = make_polygon(list(student_percentages), angles, scale)
    ax.fill(stu_xs, stu_ys, color=student_color, alpha=0.25, zorder=4)
    ax.plot(stu_xs, stu_ys, color=student_color, linewidth=2.0, zorder=5, label='Your Mark')

    # Category labels — truncate at 14 chars, positioned just outside outer ring
    for i, (cat, a) in enumerate(zip(categories, angles)):
        x_raw, y_raw = polar_to_xy(scale, a)
        # Apply separate x and y offsets so horizontal labels sit closer
        lx = x_raw * 1.05
        ly = y_raw * 1.22
        ha = 'center'
        if x_raw < -0.1: ha = 'right'
        elif x_raw > 0.1: ha = 'left'
        label = cat if len(cat) <= 7 else cat[:6] + '…'
        ax.text(lx, ly, label, ha=ha, va='center',
                fontsize=11, color=label_color, fontweight='semibold',
                fontfamily='DejaVu Sans')

    # Legend at the bottom, horizontal
    ax.legend(
        loc='upper center',
        bbox_to_anchor=(0.5, -0.02),
        ncol=3,
        fontsize=11,
        frameon=False,
        handlelength=1.5,
    )

    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)

    fig.patch.set_facecolor('white')

    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=False)
    plt.close(fig)

    return buf.getvalue().decode('utf-8')


def generate_cohort_histogram(scores, student_score=None, degree_level=None):
    """
    Generate a cohort mark distribution histogram using percentage-based bins,
    coloured by UK grade band, with a dashed vertical line for the student's mark.

    Args:
        scores: List of all student marks (already converted to percentages) in the cohort
        student_score: The specific student's mark (already converted to percentage) or None to omit
        degree_level: The degree level (e.g. 'BEng' or 'MEng/MSc')

    Returns:
        str: SVG XML string representing the vector chart
    """
    if not scores:
        return ""

    # Determine if postgraduate/M-level (where <50% is a fail)
    is_m_level = bool(
        degree_level 
        and isinstance(degree_level, str) 
        and degree_level.strip().lower().startswith('m')
    )

    # Grade band colours for each 10% bin
    band_colours = {
        0:  '#d9534f',  # Fail
        10: '#d9534f',  # Fail
        20: '#d9534f',  # Fail
        30: '#d9534f',  # Fail
        40: '#d9534f' if is_m_level else '#f0a070',  # Fail for M-level, 3rd otherwise
        50: '#7bafd4',  # 2:2
        60: '#4a90d9',  # 2:1
        70: '#74c476',  # 1st
        80: '#74c476',  # 1st
        90: '#74c476',  # 1st
    }

    fixed_bins = list(range(0, 101, 10))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    n, bins, patches = ax.hist(
        scores,
        bins=fixed_bins,
        range=(0, 100),
        edgecolor='white',
        linewidth=1.0,
        rwidth=0.85,
    )

    # Colour each bar by its grade band
    for patch, left_edge in zip(patches, fixed_bins[:-1]):
        patch.set_facecolor(band_colours.get(left_edge, '#74c476'))

    # Student mark — dashed vertical line with label above (if provided)
    if student_score is not None:
        ax.axvline(student_score, color='#3a3a3a', linestyle='--', linewidth=1.8, zorder=5)
        ax.text(
            student_score + 0.8,
            ax.get_ylim()[1] * 1.1,
            f'Your Mark',
            color='#3a3a3a',
            fontsize=16,
            va='top',
        )

    # Axes
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 10))
    ax.set_xlabel('Mark (%)', color='#475569', size=16, fontfamily='DejaVu Sans')
    ax.set_ylabel('Number of Students', color='#475569', size=16, fontfamily='DejaVu Sans')

    # Y-axis integer ticks
    max_count = int(max(n)) if len(n) > 0 else 1
    ax.set_yticks(range(0, max_count + 2))

    # Spines — all four visible to form a box
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color('#cbd5e1')

    ax.tick_params(axis='both', which='both', length=0, colors='#475569', labelsize=16)
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')

    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=False)
    plt.close(fig)

    return buf.getvalue().decode('utf-8')


def generate_module_comparison_chart(labels, student_percentages, average_percentages):
    """
    Generate a high-fidelity vector grouped bar chart comparing a student's percentage marks
    against the class average percentages for both assessment components.
    
    Args:
        labels: List of component label strings (e.g. ['Assessment 1', 'Assessment 2'])
        student_percentages: Student percentages for the components
        average_percentages: Class average percentages for the components
        
    Returns:
        str: SVG XML string representing the vector chart
    """
    if not labels:
        return ""
        
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    
    x = np.arange(len(labels))
    width = 0.30  # width of the bars
    
    student_color = '#4361ee'  # Indigo/Blue
    average_color = '#ff006e'  # Harmonious Pink/Red
    grid_color = '#cbd5e1'
    text_color = '#1e293b'
    
    # Plot bars
    ax.bar(x - width/2, student_percentages, width, label='Your Score', color=student_color, alpha=0.9, edgecolor='none', zorder=3)
    ax.bar(x + width/2, average_percentages, width, label='Class Average', color=average_color, alpha=0.5, edgecolor='none', zorder=3)
    
    # Styling
    ax.set_ylabel('Percentage (%)', color=text_color, fontweight='semibold', size=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=text_color, size=9, fontweight='semibold')
    ax.set_ylim(0, 100)
    
    # Grid lines
    ax.grid(True, axis='y', color=grid_color, linestyle=':', linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    
    # Spines
    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('#cbd5e1')
    
    ax.tick_params(axis='both', which='both', length=0, colors='#475569', labelsize=8.5)
    
    # Legend
    plt.legend(loc='upper right', fontsize=8.5, frameon=True, facecolor='white', edgecolor='#e2e8f0')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=True)
    plt.close(fig)
    
    return buf.getvalue().decode('utf-8')

