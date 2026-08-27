import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

df = pd.read_excel('comparativo_fases_minerais.xlsx')

real = df['Real (%)']
pred = df['Pred Árvore de Decisão (%)']
fases = df['Fase Mineral']


unique_fases = fases.unique()
colors = sns.color_palette('tab10', n_colors=len(unique_fases))

for i, fase in enumerate(unique_fases):
    mask = fases == fase
    ax.scatter(real[mask], pred[mask], label=fase, color=colors[i], s=70, alpha=0.8, edgecolors='k', linewidth=0.5)


min_val = 0
max_val = max(real.max(), pred.max()) + 5
ax.plot([min_val, max_val], [min_val, max_val], 'r--', label='Linha Ideal (1:1)', linewidth=1.5)


mae = (real - pred).abs().mean()
rmse = np.sqrt(((real - pred)**2).mean())
ss_res = ((real - pred)**2).sum()
ss_tot = ((real - real.mean())**2).sum()
r2 = 1 - (ss_res / ss_tot)

# Annotate metrics on plot
text_str = f'$R^2$ = {r2:.4f}\nMAE = {mae:.2f}%\nRMSE = {rmse:.2f}%'
ax.text(0.05, 0.92, text_str, transform=ax.transAxes, fontsize=11,
        verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='gray'))

ax.set_title('Real vs Predito — Árvore de Decisão (Fases Minerais DRX)', fontsize=13, fontweight='bold', pad=12)
ax.set_xlabel('Valor Real (%)', fontsize=11)
ax.set_ylabel('Valor Predito (%)', fontsize=11)
ax.set_xlim([min_val - 2, max_val])
ax.set_ylim([min_val - 2, max_val])
ax.legend(title='Fase Mineral', frameon=True, facecolor='white', edgecolor='none')
plt.tight_layout()

plt.savefig('real_vs_predito_arvore_decisao.png', dpi=300)
plt.show()