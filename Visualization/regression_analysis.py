from sklearn.linear_model import LinearRegression
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import mean_squared_error
import statsmodels.api as sm
import numpy as np
from sklearn.preprocessing import PolynomialFeatures
import statsmodels.api as sm

# Create a linear regression model

# AV_trust_analysis_simulation_results
# population_analysis_simulation_results
# fleet_size_simulation_results
data = pd.read_csv('../data/output/charging_capacity_analysis_simulation_results.csv')

## activate for AV_trust and population analysis
# data['X'] = data.apply(lambda x: x['AV_trust'].split('[')[1].split(']')[0], axis=1)
# data['X1'] = data.apply(lambda x: x['X'].split(',')[0], axis=1).astype('float')
# data['X2'] = data.apply(lambda x: x['X'].split(',')[1], axis=1).astype('float')
# data['X3'] = data.apply(lambda x: x['X'].split(',')[2], axis=1).astype('float')
# data['X4'] = data.apply(lambda x: x['X'].split(',')[3], axis=1).astype('float')
#
# X = data[['X1', 'X2', 'X3', 'X4', 'phase']].astype('float')
### activate for fleet size analysis
X = data[['charging_power', 'phase']].astype('float')
X_array = np.array(X)
degree = 1  # Choose the degree of the polynomial
poly = PolynomialFeatures(degree)
scaler = StandardScaler()
X_scaled = X.copy()
X_scaled = scaler.fit_transform(X_array)
X_poly = poly.fit_transform(X_scaled)
# X_poly = X_array


y = data['total_revenue_ride_hailing'].astype('float') * 1e-3
# y_array = np.array(y)
model = LinearRegression()
model.fit(X_poly, y)
coefficients = model.coef_
intercept = model.intercept_

# R-squared (explained variance)
r_squared = model.score(X_poly, y)

# Calculate predicted values
y_pred = model.predict(X_poly)

# Residuals (difference between actual and predicted)
residuals = y - y_pred

X_with_intercept = sm.add_constant(X_poly)  # Add a constant term for intercept
stats_model = sm.OLS(y, X_with_intercept).fit()
p_values = stats_model.pvalues
summary_str = stats_model.summary().as_text()

# Save the summary to a text file
with open('../data/output/AV_trust_analysis_regression_summary.txt', 'w') as file: # population, AV_trust
    file.write(summary_str)
print(stats_model.summary())
