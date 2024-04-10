library(ggplot2)
library(stargazer)
library(xtable)
library(dplyr)
library(tidyr)

# Read Data
data_path = "/Users/demircanm/sciebo/IS3/Research_Projects/HeterogeneousFleetManagement/01_Fleet_Sizing/3_Figures/ECIS_Sim_Results/all_simulation_results_ec_0_99_.csv"
data <- read.csv(data_path)

# Scale Distance and Duration
data$SharedKickScooter_distance <- data$SharedKickScooter_distance/1000
data$SharedScooter_distance <- data$SharedScooter_distance/1000
data$SharedCar_distance <- data$SharedCar_distance/1000

data$SharedKickScooter_duration <- data$SharedKickScooter_duration/60
data$SharedScooter_duration <- data$SharedScooter_duration/60
data$SharedCar_duration <- data$SharedCar_duration/60

# Calculate Service Quality
data$service_quality <- 0
data$service_quality <- 1-data$total_missed_trips/(data$total_fulfilled_trips+data$total_missed_trips)

#Calc. Total Distance, Duration and EC
data$distance_total = 0
data$distance_total <- data$SharedKickScooter_distance+data$SharedScooter_distance+data$SharedCar_distance

data$duration_total = 0
data$duration_total <- data$SharedKickScooter_duration+data$SharedScooter_duration+data$SharedCar_duration

data$energy_consumption_total = 0
data$energy_consumption_total <- data$SharedKickScooter_energy_consumption+data$SharedScooter_energy_consumption+data$SharedCar_energy_consumption


############################################
# Economic Perspective      ################
############################################
summary <- data %>% group_by(subs_bandwidth, price_sensitive_pop_prob) %>%
  summarise(exp_total_revenue = mean(total_revenue),
            exp_rev_ks = mean(SharedKickScooter_revenue), exp_rev_s = mean(SharedScooter_revenue), exp_rev_c = mean(SharedCar_revenue),
            exp_dis_ks = mean(SharedKickScooter_distance), exp_dis_s = mean(SharedScooter_distance), exp_dis_c = mean(SharedCar_distance),
            exp_dur_ks = mean(SharedKickScooter_duration), exp_dur_s = mean(SharedScooter_duration), exp_dur_c = mean(SharedCar_duration),
            exp_ec_ks = mean(SharedKickScooter_energy_consumption), exp_ec_s = mean(SharedScooter_energy_consumption), exp_ec_c = mean(SharedCar_energy_consumption),
            exp_total_cost = mean(total_cost_per_day),
            exp_total_profit = mean(total_revenue) - mean(total_cost_per_day),
            exp_service_quality = 1-mean(total_missed_trips/(total_fulfilled_trips+total_missed_trips)))

summary

# Format String to Latex Table
total_revenue_str <- "Exp. Total Revenue (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
total_ks_revenue_str <- "\\hspace{3.5ex}By Kick Scooter (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
total_s_revenue_str <- "\\hspace{3.5ex}By Scooter (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
total_c_revenue_str <- "\\hspace{3.5ex}By Car (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
total_profit_str <- "Exp. Total Profit (€) & %s & %s & %s & %s && %s & %s & %s &%s \\\\"
service_qual_str <- "Exp. Service Quality & %s & %s & %s & %s && %s & %s & %s &%s \\\\"

# Revenue
total_revenue_str_fr <- sprintf(total_revenue_str, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_revenue,0), nsmall=0, big.mark=",")
)

# Kick Scooter Revenue
total_ks_revenue_str_fr <- sprintf(total_ks_revenue_str, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_rev_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_rev_ks,0),nsmall=0, big.mark=",")
)

# Scooter Revenue
total_s_revenue_str_fr <- sprintf(total_s_revenue_str, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_rev_s,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_rev_s,0),nsmall=0, big.mark=",")
)

# Car Revenue
total_c_revenue_str_fr <- sprintf(total_c_revenue_str, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_rev_c,0),nsmall=0, big.mark=","),
                                  format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_rev_c,0),nsmall=0, big.mark=",")
)

# Profit
total_profit_str_fr <- sprintf(total_profit_str, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0), nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0), nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0), nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_profit,0), nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_profit,0), nsmall=0, big.mark=",")
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
service_qual_str_fr
# Copy this output to latex file
out <- paste(total_revenue_str_fr,total_ks_revenue_str_fr, total_s_revenue_str_fr, total_c_revenue_str_fr, total_profit_str_fr, service_qual_str_fr)
# Output for Latex (removes espacing char e.g., backslash)
cat(out)

############################################
# Environmental Perspective ################
############################################
summary <- data %>% group_by(subs_bandwidth, price_sensitive_pop_prob) %>%
  summarise(exp_total_trips = mean(total_fulfilled_trips), exp_total_missed_trips = mean(total_missed_trips),
            exp_ks_c = mean(SharedKickScooter_SharedCar), exp_ks_s = mean(SharedKickScooter_SharedScooter), exp_ks_ks = mean(SharedKickScooter_SharedKickScooter),
            exp_s_c = mean(SharedScooter_SharedCar), exp_s_s = mean(SharedScooter_SharedScooter), exp_s_ks = mean(SharedScooter_SharedKickScooter),
            exp_c_c = mean(SharedCar_SharedCar), exp_c_s = mean(SharedCar_SharedScooter), exp_c_ks = mean(SharedCar_SharedKickScooter),
            exp_dis_total = mean(distance_total), exp_dis_ks = mean(SharedKickScooter_distance), exp_dis_s = mean(SharedScooter_distance), exp_dis_c = mean(SharedCar_distance),
            exp_dur_total = mean(duration_total), exp_dur_ks = mean(SharedKickScooter_duration), exp_dur_s = mean(SharedScooter_duration), exp_dur_c = mean(SharedCar_duration),
            exp_ec_total = mean(energy_consumption_total), exp_ec_ks = mean(SharedKickScooter_energy_consumption), exp_ec_s = mean(SharedScooter_energy_consumption), exp_ec_c = mean(SharedCar_energy_consumption)
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

exp_dur_total = " Total Trip Duration & %s &  %s &  %s &  %s &&  %s &  %s & %s & %s \\\\"
exp_dur_ks = "\\hspace{3.5ex}Kick Scooter Trip Duration & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_dur_s = "\\hspace{3.5ex}Scooter Trip Duration & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_dur_c = "\\hspace{3.5ex}Car Trip Duration & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

# Total Trips
exp_daily_trips_fr <- sprintf(exp_daily_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_trips,0), nsmall=0, big.mark=",")
)

# Total Missed Trips
exp_daily_missed_trips_fr <- sprintf(exp_daily_missed_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0), nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=","),
                              format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_total_missed_trips,0),nsmall=0, big.mark=",")
)

#####################
# Kick Scooter Trips
#####################
exp_ks_trips_fr <- sprintf(exp_ks_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),nsmall=0, big.mark=","),
                                     format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ks_ks,0),nsmall=0, big.mark=",")
)

# KS trips that have been done with Scooter
exp_ks_s_trips_fr <- sprintf(exp_ks_s_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ks_s,0),nsmall=0, big.mark=",")
)

# KS trips that have been done with Scooter
exp_ks_c_trips_fr <- sprintf(exp_ks_c_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ks_c,0),nsmall=0, big.mark=",")
)

#####################
# Scooter Trips
#####################
exp_s_trips_fr <- sprintf(exp_s_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),nsmall=0, big.mark=","),
                           format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_s_s,0),nsmall=0, big.mark=",")
)

exp_s_ks_trips_fr <- sprintf(exp_s_ks_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_s_ks,0),nsmall=0, big.mark=",")
)

exp_s_c_trips_fr <- sprintf(exp_s_c_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_s_c,0),nsmall=0, big.mark=",")
)

#####################
# Car Trips
#####################
exp_c_trips_fr <- sprintf(exp_c_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                          format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                          format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                          format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                          format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                          format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                          format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),nsmall=0, big.mark=","),
                                 format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_c_c,0),nsmall=0, big.mark=",")
)

exp_c_ks_trips_fr <- sprintf(exp_c_ks_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                             format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),nsmall=0, big.mark=","),
                                    format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_c_ks,0),nsmall=0, big.mark=",")
)

exp_c_s_trips_fr <- sprintf(exp_c_s_trips, format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_c_s,0),nsmall=0, big.mark=",")
)

### Duration
exp_dur_total = " Total Trip Duration (h)& %s &  %s &  %s &  %s &&  %s &  %s & %s & %s \\\\"
exp_dur_ks = "\\hspace{3.5ex}By Kick Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_dur_s = "\\hspace{3.5ex}By Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_dur_c = "\\hspace{3.5ex}By Car & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

exp_dur_total_fr <- sprintf(exp_dur_total, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dur_total,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dur_total,0),nsmall=0, big.mark=",")
)

exp_dur_ks_fr <- sprintf(exp_dur_ks, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dur_ks,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dur_ks,0),nsmall=0, big.mark=",")
)

exp_dur_s_fr <- sprintf(exp_dur_s, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dur_s,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dur_s,0),nsmall=0, big.mark=",")
)

exp_dur_c_fr <- sprintf(exp_dur_c, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dur_c,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dur_c,0),nsmall=0, big.mark=",")
)

### Distance
exp_dis_total = " Total Trip Distance (km)& %s &  %s &  %s &  %s &&  %s &  %s & %s & %s \\\\"
exp_dis_ks = "\\hspace{3.5ex}By Kick Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_dis_s = "\\hspace{3.5ex}By Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_dis_c = "\\hspace{3.5ex}By Car & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

exp_dis_total_fr <- sprintf(exp_dis_total, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dis_total,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dis_total,0),nsmall=0, big.mark=",")
)

exp_dis_ks_fr <- sprintf(exp_dis_ks, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dis_ks,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dis_ks,0),nsmall=0, big.mark=",")
)

exp_dis_s_fr <- sprintf(exp_dis_s, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dis_s,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dis_s,0),nsmall=0, big.mark=",")
)

exp_dis_c_fr <- sprintf(exp_dis_c, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_dis_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_dis_c,0),nsmall=0, big.mark=",")
)

### Energy Consumption
exp_ec_total = " Total Energy Consumption (kWh) & %s &  %s &  %s &  %s &&  %s &  %s & %s & %s \\\\"
exp_ec_ks = "\\hspace{3.5ex}By Kick Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_ec_s = "\\hspace{3.5ex}By Scooter & %s & %s & %s & %s && %s & %s & %s & %s \\\\"
exp_ec_c = "\\hspace{3.5ex}By Car & %s & %s & %s & %s && %s & %s & %s & %s \\\\"

exp_ec_total_fr <- sprintf(exp_ec_total, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                            format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ec_total,0),nsmall=0, big.mark=","),
                                   format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ec_total,0),nsmall=0, big.mark=",")
)

exp_ec_ks_fr <- sprintf(exp_ec_ks, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                         format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ec_ks,0),nsmall=0, big.mark=","),
                                format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ec_ks,0),nsmall=0, big.mark=",")
)

exp_ec_s_fr <- sprintf(exp_ec_s, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ec_s,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ec_s,0), nsmall=0, big.mark=",")
)

exp_ec_c_fr <- sprintf(exp_ec_c, format(round(summary %>% filter(subs_bandwidth== 0, price_sensitive_pop_prob == 1) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 1) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 1) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 1) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0, price_sensitive_pop_prob == 0) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.05, price_sensitive_pop_prob == 0) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                        format(round(summary %>% filter(subs_bandwidth==0.1, price_sensitive_pop_prob == 0) %>% .$exp_ec_c,0),nsmall=0, big.mark=","),
                               format(round(summary %>% filter(subs_bandwidth==0.2, price_sensitive_pop_prob == 0) %>% .$exp_ec_c,0),nsmall=0, big.mark=",")
)

# Concat Partial Strings
out <- paste(exp_daily_trips_fr, exp_daily_missed_trips_fr, exp_ks_trips_fr, exp_ks_s_trips_fr,
             exp_ks_c_trips_fr, exp_s_trips_fr, exp_s_ks_trips_fr, exp_s_c_trips_fr, exp_c_trips_fr,
             exp_c_ks_trips_fr, exp_c_s_trips_fr,
             exp_dis_total_fr, exp_dis_ks_fr, exp_dis_s_fr, exp_dis_c_fr,
             exp_dur_total_fr, exp_dur_ks_fr, exp_dur_s_fr, exp_dur_c_fr,
             exp_ec_total_fr, exp_ec_ks_fr, exp_ec_s_fr, exp_ec_c_fr)
# Output for Latex
cat(out)


#########################
# Regression Analysis ###
#########################

data$subs_bandwidth_adj <- data$subs_bandwidth*100

data$subs_pop_factor <- 1.0-data$price_sensitive_pop_prob

total_profit_reg <- lm(log(total_profit) ~ subs_bandwidth_adj*subs_pop_factor, data)
sq_reg <- lm(log(service_quality) ~ subs_bandwidth_adj*subs_pop_factor, data)
energy_consum_reg <- lm(log(energy_consumption_total) ~ subs_bandwidth_adj*subs_pop_factor, data)

stargazer(total_profit_reg, sq_reg, energy_consum_reg, column.labels = c("Economic","Environmental"),column.separate = c(2,1),
          title="Regression Results", dep.var.labels=c("Total Profit","Service Quality", "Energy Consumption"),
          covariate.labels=c("Substitution Boundary (SB)","Sustainable Population (SUS)", "SB * SUS"),
          type="latex")
