import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

# Create a linear regression model

# AV_trust_analysis_simulation_results
# population_analysis_simulation_results
# fleet_size_simulation_results
# charging_capacity_analysis_simulation_results
# tech_phase_analysis_simulation_results
data = pd.read_csv("../data/output/double_MCA_P_analysis_simulation_results.csv")

## activate for AV_trust and population analysis
# AV_trust, pop_prob

data["UP"] = data.apply(lambda x: x["pop_prob"].split("[")[1].split("]")[0], axis=1)
data["UP1"] = data.apply(lambda x: x["UP"].split(",")[0], axis=1).astype("float")
data["UP2"] = data.apply(lambda x: x["UP"].split(",")[1], axis=1).astype("float")
data["UP3"] = data.apply(lambda x: x["UP"].split(",")[2], axis=1).astype("float")
data["UP4"] = data.apply(lambda x: x["UP"].split(",")[3], axis=1).astype("float")

data["AVT"] = data.apply(lambda x: x["AV_trust"].split("[")[1].split("]")[0], axis=1)
data["AVT1"] = data.apply(lambda x: x["AVT"].split(",")[0], axis=1).astype("float")
data["AVT2"] = data.apply(lambda x: x["AVT"].split(",")[1], axis=1).astype("float")
data["AVT3"] = data.apply(lambda x: x["AVT"].split(",")[2], axis=1).astype("float")
data["AVT4"] = data.apply(lambda x: x["AVT"].split(",")[3], axis=1).astype("float")


data["service"] = (
    data["total_fulfilled_trips_ride_hailing"] / data["total_trips_ride_hailing"]
)
data["revenue"] = data["total_revenue_ride_hailing"].astype("float") * 1e-3
# data = data[data['phase'] == 1]
# data = data[data['X2'] == data['X4']]
# data = data[data['X4'] == 1]
#
X = data[["MCA_adjuster", "phase"]].astype("float")

### activate for fleet size analysis
# X = data[['charging_power', 'charging_capacity', 'fleet_size', 'AV_penetration']].astype('float')
X_array = np.array(X)
degree = 1  # Choose the degree of the polynomial
poly = PolynomialFeatures(degree)
scaler = StandardScaler()
X_scaled = X_array.copy()
# X_scaled = scaler.fit_transform(X_array)
X_poly = poly.fit_transform(X_scaled)
# X_poly = X_array


# y = data['total_revenue_ride_hailing'].astype('float') * 1e-3
y = data["revenue"]
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
with open(
    "../data/output/AV_trust_analysis_regression_summary.txt", "w"
) as file:  # population, AV_trust
    file.write(summary_str)
print(stats_model.summary())
