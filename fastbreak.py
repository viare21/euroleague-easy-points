import pandas as pd
import matplotlib.pyplot as plt
import os

# ============================================================
# 0. PATHS 
# ============================================================

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()  # fallback when running cell-by-cell 

DATA_DIR = os.path.join(BASE_DIR, "..", "csv_euroleague")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

SEASONS = [f'E{y}' for y in range(2015, 2026)]

# ============================================================
# 1. LOAD DATA
# ============================================================

comparison = pd.read_csv(os.path.join(DATA_DIR, "euroleague_comparison.csv"))
header = pd.read_csv(os.path.join(DATA_DIR, "euroleague_header.csv"))

# ============================================================
# 2. DETERMINE THE WINNER OF EACH GAME (from header)
# ============================================================

games = header[header['season_code'].isin(SEASONS)][
    ['game_id', 'season_code', 'team_id_a', 'team_id_b', 'score_a', 'score_b']
].copy()

games['winner_id'] = games.apply(
    lambda row: row['team_id_a'] if row['score_a'] > row['score_b'] else row['team_id_b'],
    axis=1
)
games['margin'] = (games['score_a'] - games['score_b']).abs()

print(f"Games in scope (E2015-E2025): {len(games)}")

# ============================================================
# 3. BUILD "EASY POINTS" (fast break + second chance + turnover points)
# PER TEAM PER GAME
# ============================================================

comparison_scope = comparison[comparison['game_id'].isin(games['game_id'])].copy()

# ============================================================
# 3.1 DATA QUALITY CHECK — make sure fast break / second chance /
# turnover points are populated across the whole 2015-2025 range
# ============================================================

check_cols = [
    'fast_break_points_a', 'fast_break_points_b',
    'second_chance_points_a', 'second_chance_points_b',
    'turnover_points_a', 'turnover_points_b'
]
print("=== Missing values check (within season scope) ===")
print(comparison_scope[check_cols].isna().sum())

comparison_scope['any_missing'] = comparison_scope[check_cols].isna().any(axis=1)
print("\n=== Games with at least one missing value, by season ===")
print(comparison_scope.groupby('season_code')['any_missing'].sum())

comparison_scope['easy_points_a'] = (
    comparison_scope['fast_break_points_a']
    + comparison_scope['second_chance_points_a']
    + comparison_scope['turnover_points_a']
)
comparison_scope['easy_points_b'] = (
    comparison_scope['fast_break_points_b']
    + comparison_scope['second_chance_points_b']
    + comparison_scope['turnover_points_b']
)

# ============================================================
# 4. RESHAPE TO LONG FORMAT (one row per team per game), FLAG WIN/LOSS
# ============================================================

side_a = comparison_scope[['game_id', 'team_id_a', 'easy_points_a', 'fast_break_points_a', 'second_chance_points_a', 'turnover_points_a']].rename(
    columns={
        'team_id_a': 'team_id',
        'easy_points_a': 'easy_points',
        'fast_break_points_a': 'fast_break_points',
        'second_chance_points_a': 'second_chance_points',
        'turnover_points_a': 'turnover_points'
    }
)

side_b = comparison_scope[['game_id', 'team_id_b', 'easy_points_b', 'fast_break_points_b', 'second_chance_points_b', 'turnover_points_b']].rename(
    columns={
        'team_id_b': 'team_id',
        'easy_points_b': 'easy_points',
        'fast_break_points_b': 'fast_break_points',
        'second_chance_points_b': 'second_chance_points',
        'turnover_points_b': 'turnover_points'
    }
)

team_long = pd.concat([side_a, side_b], ignore_index=True)

team_long = team_long.merge(games[['game_id', 'winner_id']], on='game_id', how='left')
team_long['result'] = team_long.apply(
    lambda row: 'Win' if row['team_id'] == row['winner_id'] else 'Loss', axis=1
)

# ============================================================
# 5. WINNERS vs LOSERS — AVERAGE EASY POINTS PER GAME
# ============================================================

result_avg = team_long.groupby('result')[['easy_points', 'fast_break_points', 'second_chance_points', 'turnover_points']].mean().round(2)
print("\n=== Average points per game, Winners vs Losers ===")
print(result_avg)

# ============================================================
# 6. HOW OFTEN DOES THE TEAM WITH MORE EASY POINTS ACTUALLY WIN?
# ============================================================

pivot_easy = comparison_scope[['game_id', 'easy_points_a', 'easy_points_b']].merge(
    games[['game_id', 'team_id_a', 'team_id_b', 'winner_id']], on='game_id', how='left'
)

pivot_easy['easy_points_leader'] = pivot_easy.apply(
    lambda row: row['team_id_a'] if row['easy_points_a'] > row['easy_points_b']
                else (row['team_id_b'] if row['easy_points_b'] > row['easy_points_a'] else 'Tie'),
    axis=1
)

pivot_easy_no_tie = pivot_easy[pivot_easy['easy_points_leader'] != 'Tie'].copy()
pivot_easy_no_tie['leader_won'] = pivot_easy_no_tie['easy_points_leader'] == pivot_easy_no_tie['winner_id']

leader_win_rate = pivot_easy_no_tie['leader_won'].mean() * 100
print(f"\nGames where the 'easy points' leader also won the game: {leader_win_rate:.1f}%")
print(f"(Ties in easy points excluded: {len(pivot_easy) - len(pivot_easy_no_tie)} games)")

# ============================================================
# 7. CORRELATION: EASY POINTS DIFFERENTIAL vs FINAL SCORE DIFFERENTIAL
# ============================================================

comparison_scope = comparison_scope.merge(
    games[['game_id', 'score_a', 'score_b']], on='game_id', how='left'
)

comparison_scope['easy_points_diff'] = comparison_scope['easy_points_a'] - comparison_scope['easy_points_b']
comparison_scope['final_score_diff'] = comparison_scope['score_a'] - comparison_scope['score_b']

correlation = comparison_scope['easy_points_diff'].corr(comparison_scope['final_score_diff'])
print(f"\nCorrelation (easy points differential vs final score differential): {correlation:.3f}")

# ============================================================
# 8. PLOT 1: WINNERS vs LOSERS — BAR CHART
# ============================================================

BG_COLOR = '#0a1f3d'
WIN_COLOR = '#90EE90'
LOSS_COLOR = '#FF7F7F'

fig_bar, ax = plt.subplots(figsize=(7, 5.5))
fig_bar.patch.set_facecolor(BG_COLOR)
ax.set_facecolor(BG_COLOR)

categories = ['Fast break', 'Second chance', 'Turnover points', 'Easy points\n(combined)']
win_vals = [
    result_avg.loc['Win', 'fast_break_points'],
    result_avg.loc['Win', 'second_chance_points'],
    result_avg.loc['Win', 'turnover_points'],
    result_avg.loc['Win', 'easy_points']
]
loss_vals = [
    result_avg.loc['Loss', 'fast_break_points'],
    result_avg.loc['Loss', 'second_chance_points'],
    result_avg.loc['Loss', 'turnover_points'],
    result_avg.loc['Loss', 'easy_points']
]

x = range(len(categories))
width = 0.35

bars_win = ax.bar([i - width/2 for i in x], win_vals, width, label='Winners', color=WIN_COLOR)
bars_loss = ax.bar([i + width/2 for i in x], loss_vals, width, label='Losers', color=LOSS_COLOR)

ax.set_xticks(x)
ax.set_xticklabels(categories, color='white')
ax.set_ylabel('Points per game', color='white')
ax.set_title('Fast break, second chance & turnover points\nWinners vs Losers (2015-2025)', color='white')

ax.tick_params(colors='white')
for spine in ax.spines.values():
    spine.set_color('white')

legend = ax.legend(facecolor=BG_COLOR, edgecolor='white')
plt.setp(legend.get_texts(), color='white')

for bars in [bars_win, bars_loss]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.15, f'{height:.1f}', ha='center', fontweight='bold', color='white', fontsize=9)

plt.tight_layout()
fig_bar.savefig(os.path.join(IMAGES_DIR, 'winners_vs_losers_easy_points.png'), dpi=150, facecolor=fig_bar.get_facecolor(), pad_inches=0.3)
plt.show()

# ============================================================
# 9. PLOT 2: SCATTER — EASY POINTS DIFFERENTIAL vs FINAL SCORE DIFFERENTIAL
# ============================================================

fig_scatter, ax = plt.subplots(figsize=(7.5, 6.5))
fig_scatter.patch.set_facecolor(BG_COLOR)
ax.set_facecolor(BG_COLOR)

ax.scatter(comparison_scope['easy_points_diff'], comparison_scope['final_score_diff'],
           alpha=0.25, s=15, color=WIN_COLOR)

ax.axhline(0, color='white', linewidth=0.8)
ax.axvline(0, color='white', linewidth=0.8)

ax.set_xlabel('Easy points differential (Team A − Team B)', color='white')
ax.set_ylabel('Final score differential (Team A − Team B)', color='white')
ax.set_title(f'Easy points vs final score differential\ncorrelation = {correlation:.2f}', color='white')

ax.tick_params(colors='white')
for spine in ax.spines.values():
    spine.set_color('white')

plt.tight_layout()
fig_scatter.savefig(os.path.join(IMAGES_DIR, 'easy_points_vs_score_diff_scatter.png'), dpi=150, facecolor=fig_scatter.get_facecolor(), pad_inches=0.3)
plt.show()