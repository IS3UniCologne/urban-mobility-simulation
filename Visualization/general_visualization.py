import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def set_style():
    # This sets reasonable defaults for font size for a figure that will go in a paper
    sns.set_context("paper")

    # Set the font to be serif, rather than sans
    sns.set(font='serif')
    # sns.set_color_codes("pastel")
    sns.set_palette("mako", n_colors=2)
    # Make the background white, and specify the font family
    sns.set_style("ticks", {
        "font.family": "serif",
        "font.serif": ["Times", "Palatino", "serif"]
    })


# Create a linear regression model

key = 'AVT_UP'
Y = 'SQ'
data = pd.read_csv(f'../data/output/chicago/double_{key}_analysis_simulation_results.csv')

## activate for AV_trust and population analysis
# AV_trust, pop_prob

data['UP'] = data.apply(lambda x: x['pop_prob'].split('[')[1].split(']')[0], axis=1)
data['UP1'] = data.apply(lambda x: x['UP'].split(',')[0], axis=1).astype('float')
data['UP2'] = data.apply(lambda x: x['UP'].split(',')[1], axis=1).astype('float')
data['UP3'] = data.apply(lambda x: x['UP'].split(',')[2], axis=1).astype('float')
data['UP4'] = data.apply(lambda x: x['UP'].split(',')[3], axis=1).astype('float')

data['AVT'] = data.apply(lambda x: x['AV_trust'].split('[')[1].split(']')[0], axis=1)
data['AVT1'] = data.apply(lambda x: x['AVT'].split(',')[0], axis=1).astype('float')
data['AVT2'] = data.apply(lambda x: x['AVT'].split(',')[1], axis=1).astype('float')
data['AVT3'] = data.apply(lambda x: x['AVT'].split(',')[2], axis=1).astype('float')
data['AVT4'] = data.apply(lambda x: x['AVT'].split(',')[3], axis=1).astype('float')

data['revenue'] = data['total_revenue_ride_hailing'] * 1e-3
data['SQ'] = data['total_fulfilled_trips_ride_hailing'] / data['total_trips_ride_hailing']
# data = data[data['phase'] == 1]
# data = data[data['X2'] == data['X4']]
# data = data[data['X3'] == data['X4']]
# data = data[data['X1'] == data['X4']]
# data = data[data['X1'] == 1]
df = data.copy()

if key == "P":
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(12, 8), constrained_layout=True)
    # 1D

    df = data.copy()
    set_style()

    sns.lineplot(data=df, x='phase', y=Y, ci=100, hue="seed", legend=False, ax=ax)
    # ax[k][j].set_ylim(0, 1)
    ax.set_xlabel('AV Penetration', fontsize=12)
    if Y == 'revenue':
        ax.set_ylabel('revenue (k$)', fontsize=12)
    if Y == 'SQ':
        ax.set_ylabel('SQ (%)', fontsize=12)
    # ax[k][j].set_title(f'User Population={a[i]}', fontsize=12)


if key == "P_UP":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = ['UP1', 'UP2', 'UP3', 'UP4']
    for i in range(4):
        df = data.copy()
        df = df[df[a[i]] == 1]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='phase', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        # ax[k][j].set_ylim(0, 70)
        ax[k][j].set_xlabel('AV Penetration', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'User Population={a[i]}', fontsize=12)


if key == "FS_P":

    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = [0.25, 0.50, 0.75, 1.0]
    for i in range(4):
        df = data.copy()
        df = df[df['AV_penetration'] == a[i]]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='fleet_size', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        # ax[k][j].set_ylim(0.05, 0.55)
        ax[k][j].set_xlabel('# cars', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'AV_penetration={a[i]}', fontsize=12)


if key == "AVP_P":

    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = [0.25, 0.50, 0.75, 1.0]
    for i in range(4):
        df = data.copy()
        df = df[df['phase'] == a[i]]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='AV_price_reduction', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        # ax[k][j].set_ylim(10, 33)
        ax[k][j].set_xlabel('AV_price_fraction', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'AV_penetration={a[i]}', fontsize=12)


if key == "UP_P":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = [0.25, 0.50, 0.75, 1.0]
    for i in range(4):
        df = data.copy()
        df = df[df['AV_penetration'] == a[i]]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='UP1', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        # ax[k][j].set_ylim(0, 80)
        ax[k][j].set_xlabel('Population penetration', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'AV_penetration={a[i]}', fontsize=12)


if key == "AVT_P":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = [0.25, 0.50, 0.75, 1.0]
    for i in range(4):
        df = data.copy()
        df = df[df['AV_penetration'] == a[i]]
        set_style()
        df = df[(df.AVT1 == df.AVT2) & (df.AVT2 == df.AVT4) & (df.AVT2 == df.AVT3)]
        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='AVT2', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        # ax[k][j].set_ylim(0, 80)
        ax[k][j].set_xlabel('Autonomous Trust', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'AV_penetration={a[i]}', fontsize=12)


if key == "MCA_P":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = [0.25, 0.50, 0.75, 1.0]
    for i in range(4):
        df = data.copy()
        df = df[df['phase'] == a[i]]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='MCA_adjuster', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        # ax[k][j].set_ylim(10, 33)
        ax[k][j].set_xlabel('MCA', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'AV_penetration={a[i]}', fontsize=12)


if key == "FS_UP":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = ['UP1', 'UP2', 'UP3', 'UP4']
    for i in range(4):
        df = data.copy()
        df = df[df[a[i]] == 1]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='fleet_size', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        ax[k][j].set_ylim(0, 70)
        ax[k][j].set_xlabel('AV Penetration', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'User Population={a[i]}', fontsize=12)


if key == "AVP_UP":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = ['UP1', 'UP2', 'UP3', 'UP4']
    for i in range(4):
        df = data.copy()
        df = df[df[a[i]] == 1]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='AV_price_reduction', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        ax[k][j].set_ylim(0, 70)
        ax[k][j].set_xlabel('AV Penetration', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'User Population={a[i]}', fontsize=12)


if key == "AVT_UP":
    fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 8), constrained_layout=True)
    # 1D
    a = ['UP1', 'UP2', 'UP3', 'UP4']
    for i in range(4):
        df = data.copy()
        df = df[df[a[i]] == 1]
        set_style()

        k, j = divmod(i, 2)
        # ax[k][j].scatter(df.AV_price_reduction, df.service)
        sns.lineplot(data=df, x='AVT1', y=Y, ci=100, hue="seed", legend=False, ax=ax[k][j])
        ax[k][j].set_xlabel('AV Penetration', fontsize=12)
        if Y == 'revenue':
            ax[k][j].set_ylabel('revenue (k$)', fontsize=12)
        if Y == 'SQ':
            ax[k][j].set_ylabel('SQ (%)', fontsize=12)
        ax[k][j].set_title(f'User Population={a[i]}', fontsize=12)

plt.savefig(f"/home/rahadi/Projects/UBS-Chicago/data/output/{key}_{Y}.pdf")
plt.show()


# 2D
# fig = plt.figure()
# ax = Axes3D(fig)
# ax.plot_trisurf(df.phase, df.AV_price_reduction, df.revenue, linewidth=0.2)
# plt.show()
