import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

'''
gdf = df.groupby(['sampler', 'example'])
R = gdf.agg({'ks': np.mean, 'ESS': np.median, 'N': mp.max})
# TODO assert same as min
R['real_ess'] = ref / R['ks']
R['eff'] = R['real_ess'] / R['N']
'''

# rcParams['axes.color_cycle']
# from matplotlib import rcParams
# TODO plot on outside

# TODO do groupby to aggregate over dims
# TODO adds lines between dims on same example

def plot_ess(df, groupby_col, metric, pooled=False):
    gdf = df.groupby(groupby_col)
    metric = metric + '_pooled' if pooled else metric

    plt.figure()
    for name, sub_df in gdf:
        n_chains = sub_df['n_chains'].values

        real_ess = 1.0 / sub_df[metric].values  # TODO change ref in num
        estimated_ess = sub_df['ESS'].values if pooled else \
            sub_df['ESS'].values / n_chains
        plt.loglog(estimated_ess, real_ess, '.', label=name, alpha=0.5)
    xgrid = np.logspace(0.0, 6.0, 100)  # TODO automatic
    plt.loglog(xgrid, xgrid, 'k--')
    plt.legend()
    plt.grid('on')
    plt.xlabel('ESS')
    plt.ylabel('real ESS')
    plt.title(metric)



def plot_eff(df, groupby_col, metric, pooled=False):
    gdf = df.groupby(groupby_col)
    metric = metric + '_pooled' if pooled else metric

    plt.figure()
    for name, sub_df in gdf:
        n_chains = sub_df['n_chains'].values
        n_samples = sub_df['N'].values

        real_ess = 1.0 / sub_df[metric].values  # TODO change ref in num
        real_eff = real_ess / n_samples

        estimated_ess = sub_df['ESS'].values if pooled else \
            sub_df['ESS'].values / n_chains
        estimated_eff = estimated_ess / n_samples

        plt.loglog(estimated_eff, real_eff, '.', label=name, alpha=0.5)
    xgrid = np.logspace(-6.0, 0.0, 100)  # TODO automatic
    plt.loglog(xgrid, xgrid, 'k--')
    plt.legend()
    plt.grid('on')
    plt.xlabel('estimated efficiency')
    plt.ylabel('real efficiency')
    plt.title(metric)




# TODO config
#fname = '../../sampler-local/full_size/phase4/perf_sync.csv'

fname = '../perf_sync.csv'
df = pd.read_csv(fname, header=0, index_col=None)



'''
examples = df['example'].unique()
samplers = df['sampler'].unique()

plt.figure()
for ex in examples:
    idx = df['example'] == ex
    real_ess = 1.0 / df.loc[idx, 'mean'].values
    plt.loglog(df.loc[idx, 'ESS'].values, real_ess, '.', label=ex)


plt.figure()
for sam in samplers:
    idx = df['sampler'] == sam
    df_sub = df.loc[idx, :]

    real_ess = 1.0 / df_sub['mean'].values
    n_samples = df_sub['N'].values
    n_chains = df_sub['n_chains'].values
    estimated_ess = df_sub['ESS'].values / n_chains
    plt.loglog(estimated_ess, real_ess, '.', label=sam, alpha=0.5)
xgrid = np.logspace(0.0, 6.0, 100)
plt.loglog(xgrid, xgrid, 'k--')
plt.legend()
plt.xlabel('ESS')
plt.ylabel('real ESS')
plt.title('mean')


plt.figure()
for sam in samplers:
    idx = df['sampler'] == sam
    df_sub = df.loc[idx, :]

    real_ess = 1.0 / df_sub['mean'].values
    n_samples = df_sub['N'].values
    n_chains = df_sub['n_chains'].values
    eff = real_ess / n_samples
    estimated_eff = df_sub['ESS'].values / (n_samples * n_chains)
    plt.loglog(estimated_eff, eff, '.', label=sam, alpha=0.5)
xgrid = np.logspace(-6.0, 0.0, 100)
plt.loglog(xgrid, xgrid, 'k--')
plt.legend()
plt.xlabel('estimated efficiency')
plt.ylabel('real efficiency')
plt.title('mean')

plt.figure()
for sam in samplers:
    idx = df['sampler'] == sam
    df_sub = df.loc[idx, :]

    real_ess = 1.0 / df_sub['mean_pooled'].values
    n_samples = df_sub['N'].values
    n_chains = df_sub['n_chains'].values
    eff = real_ess / (n_samples * n_chains)
    estimated_eff = df_sub['ESS'].values / (n_samples * n_chains)
    plt.loglog(estimated_eff, eff, '.', label=sam, alpha=0.5)
xgrid = np.logspace(-6.0, 0.0, 100)
plt.loglog(xgrid, xgrid, 'k--')
plt.legend()
plt.xlabel('estimated efficiency')
plt.ylabel('real efficiency')
plt.title('mean pooled')
'''
