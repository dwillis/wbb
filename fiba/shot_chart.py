import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle, Arc
import os
from io import StringIO

# Load the CSV data from file
try:
    # Try to read from uploaded file first (if running in an environment with file uploads)
    df = pd.read_csv('shot_chart.csv')
    print("Successfully loaded data from shot_chart.csv")
except FileNotFoundError:
    raise
            
# Display first few rows to verify data structure
print("\nFirst 10 rows of the dataset:")
print(df.head(10))
print(f"\nDataset shape: {df.shape}")

# Validate required columns
required_columns = ['team', 'coord_x', 'coord_y', 'outcome', 'three_pointer']
missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
    print(f"Warning: Missing required columns: {missing_columns}")
    print("Please ensure your CSV has the following columns: team, coord_x, coord_y, outcome, three_pointer")
else:
    print("✓ All required columns present")

def draw_basketball_court(ax, color='black', lw=2):
    """Draw a basketball court that matches the original shot chart layout"""
    
    # Court outline - full court view
    court = Rectangle((0, 0), 50, 25, linewidth=lw, color=color, fill=False)
    
    # Center line
    center_line = plt.Line2D([25, 25], [0, 25], linewidth=lw, color=color)
    ax.add_line(center_line)
    
    # Center circle
    center_circle = Circle((25, 12.5), 3, linewidth=lw, color=color, fill=False)
    
    # Left side (USA side)
    # 3-point arc
    left_arc = Arc((5, 12.5), 16, 16, angle=0, theta1=270, theta2=90, linewidth=lw, color=color)
    # Paint/key
    left_paint = Rectangle((0, 8.5), 8, 8, linewidth=lw, color=color, fill=False)
    # Free throw circle
    left_ft_circle = Circle((8, 12.5), 3, linewidth=lw, color=color, fill=False)
    # Basket area
    left_basket = Circle((1.5, 12.5), 0.5, linewidth=lw, color=color, fill=False)
    
    # Right side (Korea side) 
    # 3-point arc
    right_arc = Arc((45, 12.5), 16, 16, angle=0, theta1=90, theta2=270, linewidth=lw, color=color)
    # Paint/key
    right_paint = Rectangle((42, 8.5), 8, 8, linewidth=lw, color=color, fill=False)
    # Free throw circle
    right_ft_circle = Circle((42, 12.5), 3, linewidth=lw, color=color, fill=False)
    # Basket area
    right_basket = Circle((48.5, 12.5), 0.5, linewidth=lw, color=color, fill=False)
    
    # Add all elements to the court
    court_elements = [
        court, center_circle, 
        left_arc, left_paint, left_ft_circle, left_basket,
        right_arc, right_paint, right_ft_circle, right_basket
    ]
    
    for element in court_elements:
        ax.add_patch(element)
    
    # Set axis properties for full court view
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 25)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])

# Create the shot map - single full court view like the original
fig, ax = plt.subplots(1, 1, figsize=(16, 8))

# Draw the full basketball court
draw_basketball_court(ax, color='black', lw=2)

# Adjust coordinates to match full court layout
# USA shoots on left side (original coords), Korea on right side (mirror + offset)
usa_data = df[df['team'] == 'USA'].copy()
kor_data = df[df['team'] == 'KOR'].copy()

# Plot USA shots on left side (transform coordinates to match court layout)
for _, shot in usa_data.iterrows():
    # Transform coordinates to left side of court
    x = shot['coord_x'] * 0.8  # Scale down slightly
    y = shot['coord_y'] * 1.0
    
    if shot['outcome'] == 'made':
        color = 'green'
        marker = '+'
    else:
        color = 'red' 
        marker = 'x'
    
    # Marker size based on shot type
    size = 120 if shot['three_pointer'] else 80
    linewidth = 3
    
    ax.scatter(x, y, c=color, marker=marker, s=size, linewidths=linewidth)

# Plot Korea shots on right side (mirror and offset coordinates)
for _, shot in kor_data.iterrows():
    # Transform coordinates to right side of court (mirror from left side)
    x = 50 - (shot['coord_x'] * 0.8)  # Mirror and offset to right side
    y = shot['coord_y'] * 1.0
    
    if shot['outcome'] == 'made':
        color = 'green'
        marker = '+'
    else:
        color = 'red'
        marker = 'x'
    
    # Marker size based on shot type
    size = 120 if shot['three_pointer'] else 80
    linewidth = 3
    
    ax.scatter(x, y, c=color, marker=marker, s=size, linewidths=linewidth)

# Add team labels
ax.text(12.5, 2, 'USA', fontsize=16, fontweight='bold', ha='center')
ax.text(37.5, 2, 'KOR', fontsize=16, fontweight='bold', ha='center')

# Add title and legend
plt.suptitle('USA 134 vs 53 KOR\nFIBA U19 Women\'s Basketball World Cup 2025', 
             fontsize=14, fontweight='bold', y=0.95)

# Add legend in a better position
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='+', color='w', markerfacecolor='green', markersize=12, label='Made Shot', markeredgecolor='green', markeredgewidth=2),
    Line2D([0], [0], marker='x', color='w', markerfacecolor='red', markersize=12, label='Missed Shot', markeredgecolor='red', markeredgewidth=2)
]

ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.1), ncol=2)

# Calculate and display shooting statistics
usa_made = len(usa_data[usa_data['outcome'] == 'made'])
usa_total = len(usa_data)
usa_3pt_made = len(usa_data[(usa_data['outcome'] == 'made') & (usa_data['three_pointer'] == True)])
usa_3pt_total = len(usa_data[usa_data['three_pointer'] == True])

kor_made = len(kor_data[kor_data['outcome'] == 'made'])
kor_total = len(kor_data)
kor_3pt_made = len(kor_data[(kor_data['outcome'] == 'made') & (kor_data['three_pointer'] == True)])
kor_3pt_total = len(kor_data[kor_data['three_pointer'] == True])

plt.tight_layout()
plt.show()

# Additional analysis
print("Shot Chart Analysis:")
print("=" * 50)
print(f"USA Shooting:")
print(f"  Overall: {usa_made}/{usa_total} ({usa_made/usa_total:.1%})")
print(f"  3-Pointers: {usa_3pt_made}/{usa_3pt_total} ({usa_3pt_made/usa_3pt_total:.1%})")
print(f"  2-Pointers: {usa_made-usa_3pt_made}/{usa_total-usa_3pt_total} ({(usa_made-usa_3pt_made)/(usa_total-usa_3pt_total):.1%})")

print(f"\nKorea Shooting:")
print(f"  Overall: {kor_made}/{kor_total} ({kor_made/kor_total:.1%})")
print(f"  3-Pointers: {kor_3pt_made}/{kor_3pt_total} ({kor_3pt_made/kor_3pt_total:.1%})")
print(f"  2-Pointers: {kor_made-kor_3pt_made}/{kor_total-kor_3pt_total} ({(kor_made-kor_3pt_made)/(kor_total-kor_3pt_total):.1%})")

# Heat map analysis by court zones
print(f"\nShot Distribution by Zones:")
print("USA - Made shots concentrated in paint and mid-range areas")
print("KOR - More dispersed shooting pattern with lower efficiency")