library(ggplot2)
library(stargazer)
library(xtable)
library(dplyr)
library(tidyr)

# Read Data
data_path = "/Users/demircanm/Desktop/all_simulation_results.csv"
data <- read.csv(data_path)


# Calculate Service Quality
data$service_quality <- 0
data$service_quality <- 1-data$total_missed_trips/(data$total_fulfilled_trips+data$total_missed_trips)

############################################
# Economic Perspective      ################
############################################
summary <- data %>% group_by(subs_bandwidth, price_sensitive_pop_prob) %>% 
  summarise(exp_total_revenue = mean(total_revenue), exp_total_cost = mean(total_cost_per_day),
            exp_total_profit = mean(total_revenue) - mean(total_cost_per_day), 
            exp_service_quality = 1-mean(total_missed_trips/(total_fulfilled_trips+total_missed_trips)))

# Format String to Latex Table
total_revenue_str <- "Exp. Total Revenue (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
total_profit_str <- "Exp. Total Profit (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
service_qual_str <- "Exp. Service Quality & %s & %s & %s & %s && %s & %s & %s &%s \\\\"

# Revenue
total_revenue_str_fr <- sprintf(total_revenue_str, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0),
        round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0)
        )

# Profit
total_profit_str_fr <- sprintf(total_profit_str, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0),
                                round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0)
)

# Service Quality
service_qual_str_fr<- sprintf(service_qual_str, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_service_quality,2),
                               round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_service_quality,2)
)

# Copy this output to latex file
out <- paste(total_revenue_str_fr, total_profit_str_fr, service_qual_str_fr)
# Output for Latex (removes espacing char e.g., backslash)
cat(out)

############################################
# Environmental Perspective ################
############################################

summary <- data %>% group_by(subs_bandwidth, price_sensitive_pop_prob) %>% 
  summarise(exp_total_trips = mean(total_fulfilled_trips), exp_total_missed_trips = mean(total_missed_trips), 
            exp_ks_c = mean(SharedKickScooter_SharedCar), exp_ks_s = mean(SharedKickScooter_SharedScooter), exp_ks_ks = mean(SharedKickScooter_SharedKickScooter),
            exp_s_c = mean(SharedScooter_SharedCar), exp_s_s = mean(SharedScooter_SharedScooter), exp_s_ks = mean(SharedScooter_SharedKickScooter),
            exp_c_c = mean(SharedCar_SharedCar), exp_c_s = mean(SharedCar_SharedScooter), exp_c_ks = mean(SharedCar_SharedKickScooter)
  )


exp_daily_trips = "Exp. Daily Fulfilled Trips & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_daily_missed_trips = "Daily Missed Trips & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

exp_ks_trips = " Kick Scooter Trips ($N_{ks}$) & %s &  %s &  %s &  %s &&  %s &  %s & %s & %s \\\\"
exp_ks_s_trips = "\\hspace{3.5ex}Kick Scooter $\\succ$ Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_ks_c_trips = "\\hspace{3.5ex}Kick Scooter $\\succ$ Car & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

exp_s_trips = "Scooter Trips ($N_{s}$) & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_s_ks_trips = "\\hspace{3.5ex}Scooter $\\succ$ Kick Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_s_c_trips = "\\hspace{3.5ex}Scooter $\\succ$ Car & %s & %s & %s & %s && %s & %s & %s & %s  \\\\"

exp_c_trips = "Car Trips ($N_{c}$) & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_c_ks_trips = "\\hspace{3.5ex}Car $\\succ$ Kick Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_c_s_trips = "\\hspace{3.5ex}Car $\\succ$ Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

# Total Trips
exp_daily_trips_fr <- sprintf(exp_daily_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0),
                                round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0)
)

# Total Missed Trips
exp_daily_missed_trips_fr <- sprintf(exp_daily_missed_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),
                              round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0)
)

#####################
# Kick Scooter Trips
#####################
exp_ks_trips_fr <- sprintf(exp_ks_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),
                                     round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0)
)

# KS trips that have been done with Scooter
exp_ks_s_trips_fr <- sprintf(exp_ks_s_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0)
)

# KS trips that have been done with Scooter
exp_ks_c_trips_fr <- sprintf(exp_ks_c_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0)
)

#####################
# Scooter Trips
#####################
exp_s_trips_fr <- sprintf(exp_s_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),
                           round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0)
)

exp_s_ks_trips_fr <- sprintf(exp_s_ks_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0)
)

exp_s_c_trips_fr <- sprintf(exp_s_c_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0)
)

#####################
# Car Trips
#####################
exp_c_trips_fr <- sprintf(exp_c_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),
                          round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0)
)

exp_c_ks_trips_fr <- sprintf(exp_c_ks_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),
                             round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0)
)

exp_c_s_trips_fr <- sprintf(exp_c_s_trips, round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),
                            round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0)
)

# Concat Partial Strings
out <- paste(exp_daily_trips_fr, exp_daily_missed_trips_fr, exp_ks_trips_fr, exp_ks_s_trips_fr, exp_ks_c_trips_fr, exp_s_trips_fr, exp_s_ks_trips_fr, exp_s_c_trips_fr, exp_c_trips_fr, exp_c_ks_trips_fr, exp_c_s_trips_fr)
# Output for Latex
cat(out)


#########################
# Regression Analysis ###
#########################

data$subs_bandwidth_adj <- data$subs_bandwidth*100

revenue_reg <- lm(log(total_revenue) ~ subs_bandwidth_adj*price_sensitive_pop_prob, data)
sq_reg <- lm(log(service_quality) ~ subs_bandwidth_adj*price_sensitive_pop_prob, data)
cars_reg <- lm(log(SharedCar_SharedCar) ~ subs_bandwidth_adj*price_sensitive_pop_prob, data)
ks_reg <- lm(log(SharedKickScooter_SharedKickScooter) ~ subs_bandwidth_adj*price_sensitive_pop_prob, data)
s_reg <- lm(log(SharedScooter_SharedScooter) ~ subs_bandwidth_adj*price_sensitive_pop_prob, data)


stargazer(revenue_reg, sq_reg, ks_reg, s_reg, cars_reg, column.labels = c("Economic","Environmental"),column.separate = c(2,3),
          title="Regression Results", dep.var.labels=c("Revenue","Service Quality", "Kick Scooter Trips", "Scooter Trips", "Car Trips"),
          covariate.labels=c("Substitution Boundary (SB)","Price-Sensitive Population (PSP)", "SB * PSP"),
          type="latex")
