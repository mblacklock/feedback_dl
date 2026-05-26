"""Matplotlib-based server-side SVG chart generation utilities."""
import io
import numpy as np
import matplotlib
# Use non-interactive Agg backend to avoid GUI threads/issues
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def generate_radar_chart(categories, student_percentages, average_percentages):
    """
    Generate a high-fidelity vector radar chart comparing a student's marks
    against the class average in percentage terms (0-100%).
    
    Args:
        categories: List of category label strings
        student_percentages: List of student percentages matching the categories
        average_percentages: List of class average percentages matching the categories
        
    Returns:
        str: SVG XML string representing the vector chart
    """
    # Number of variables/categories
    num_vars = len(categories)
    if num_vars == 0:
        return ""

    # Compute angle for each category (closed loop)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    
    # Close the loop for polar plot
    angles += angles[:1]
    student_vals = list(student_percentages) + list(student_percentages)[:1]
    avg_vals = list(average_percentages) + list(average_percentages)[:1]
    
    # Styling variables
    student_color = '#4361ee'  # Sleek Indigo/Blue
    average_color = '#ff006e'  # Vibrantly harmonized Pink/Red
    grid_color = '#e2e8f0'      # Clean slate border
    text_color = '#1e293b'      # Dark slate text
    
    fig, ax = plt.subplots(figsize=(4.5, 4.5), subplot_kw=dict(projection='polar'))
    
    # Draw category labels
    plt.xticks(angles[:-1], categories, color=text_color, size=9, fontweight='semibold')
    
    # Draw student data
    ax.plot(angles, student_vals, color=student_color, linewidth=2.5, linestyle='solid', label='Student')
    ax.fill(angles, student_vals, color=student_color, alpha=0.15)
    
    # Draw average data
    ax.plot(angles, avg_vals, color=average_color, linewidth=2, linestyle='dashed', label='Class Average')
    ax.fill(angles, avg_vals, color=average_color, alpha=0.08)
    
    # Y-axis configurations (0 to 100%)
    ax.set_ylim(0, 100)
    ax.set_rlabel_position(30)
    plt.yticks([20, 40, 60, 80, 100], ["20%", "40%", "60%", "80%", "100%"], color='#64748b', size=8)
    
    # Grid styling
    ax.grid(True, color=grid_color, linestyle='-', linewidth=0.5)
    ax.spines['polar'].set_visible(False)
    
    # Legend
    plt.legend(loc='upper right', bbox_to_anchor=(1.25, 1.15), fontsize=8.5, frameon=True, facecolor='white', edgecolor=grid_color)
    
    # Save to buffer as SVG
    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=True)
    plt.close(fig)
    
    return buf.getvalue().decode('utf-8')


def generate_cohort_histogram(scores, student_score, max_score=100, subdivision="none"):
    """
    Generate a class distribution histogram showing cohort final marks,
    along with a clear visual vertical line highlighting the current student's score.
    
    Args:
        scores: List of all student marks in the cohort
        student_score: The specific student's score
        max_score: Maximum possible marks for the assessment
        subdivision: The grading subdivision mode
        
    Returns:
        str: SVG XML string representing the vector chart
    """
    if not scores:
        return ""
        
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    
    # Color palette
    bar_color = '#94a3b8'         # Clean, soft slate blue for background bars
    highlight_color = '#ff006e'   # Vibrant pink/red for vertical line
    avg_color = '#3b82f6'         # Blue for average
    text_color = '#1e293b'
    grid_color = '#f1f5f9'
    
    # Calculate bins dynamically
    num_bins = min(15, max(5, int(max_score / 5)))
    
    # Plot histogram
    n, bins, patches = ax.hist(scores, bins=num_bins, range=(0, max_score), 
                               color=bar_color, edgecolor='#f8fafc', linewidth=1.2, alpha=0.85, rwidth=0.9)
    
    # Plot Student score vertical line
    ax.axvline(student_score, color=highlight_color, linestyle='-', linewidth=2.5, 
               label=f"Your Mark ({student_score})")
    
    # Plot Class Average vertical line
    cohort_avg = np.mean(scores)
    ax.axvline(cohort_avg, color=avg_color, linestyle='--', linewidth=2, 
               label=f"Class Average ({cohort_avg:.1f})")
    
    # Styling axes
    ax.set_xlim(0, max_score)
    ax.set_xlabel('Marks', color=text_color, fontweight='semibold', size=9.5)
    ax.set_ylabel('Number of Students', color=text_color, fontweight='semibold', size=9.5)
    
    # Standard grid lines
    ax.grid(True, axis='y', color='#e2e8f0', linestyle=':', linewidth=0.8)
    ax.set_axisbelow(True)
    
    # Turn off outer border spines
    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('#cbd5e1')
    
    # Tick formatting
    ax.tick_params(axis='both', which='both', length=0, colors='#475569', labelsize=8.5)
    
    # Legend
    plt.legend(loc='upper right', fontsize=8.5, frameon=True, facecolor='white', edgecolor='#e2e8f0')
    
    # Save to buffer as SVG
    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=True)
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

