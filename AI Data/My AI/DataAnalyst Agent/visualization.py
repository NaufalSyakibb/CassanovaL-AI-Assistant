import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

df = pd.read_csv(r'C:\Users\muham\OneDrive\Dokumen\Python\ai_python\AI Data\My AI\DataAnalyst Agent\customers-100.csv')
NUM = ['index']
CAT = []

# Fig 1 — Correlation heatmap
corr = df[NUM].corr().round(2)
fig = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r',
                title='Correlation Heatmap', template='plotly_dark')
fig.write_html('fig1_heatmap.html'); fig.show()

# Fig 2 — Feature distributions
fig2 = make_subplots(rows=2, cols=3, subplot_titles=NUM[:6])
for i, col in enumerate(NUM[:6]):
    r, c = i // 3 + 1, i % 3 + 1
    fig2.add_trace(go.Histogram(x=df[col].dropna(), name=col, showlegend=False), row=r, col=c)
fig2.update_layout(title='Feature Distributions', template='plotly_dark')
fig2.write_html('fig2_distributions.html'); fig2.show()

# Fig 3 — Box plots
fig3 = go.Figure([go.Box(y=df[col].dropna(), name=col) for col in NUM[:8]])
fig3.update_layout(title='Box Plots — Outlier Overview', template='plotly_dark')
fig3.write_html('fig3_boxplots.html'); fig3.show()