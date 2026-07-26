# 修士発展編：モデル評価と支援プロセスの確認
# content/R を作業ディレクトリとして実行してください。

library(tidyverse)
library(broom)
library(yardstick)

learner_week <- read_csv(
  "../../assets/data/learner-week.csv",
  show_col_types = FALSE
)
intervention <- read_csv(
  "../../assets/data/intervention.csv",
  show_col_types = FALSE
)

features <- learner_week |>
  filter(week <= 3) |>
  group_by(learner_key, study_schedule) |>
  summarise(
    active_days_w1_3 = sum(active_days),
    mean_score_w1_3 = mean(avg_score),
    .groups = "drop"
  )

outcome <- learner_week |>
  filter(week >= 4) |>
  group_by(learner_key) |>
  summarise(
    all_future_on_time = as.integer(all(assignments_on_time == 1)),
    .groups = "drop"
  )

model_data <- inner_join(features, outcome, by = "learner_key")

set.seed(20260726)
train_ids <- sample(
  model_data$learner_key,
  size = floor(0.7 * nrow(model_data))
)

train <- model_data |> filter(learner_key %in% train_ids)
test <- model_data |> filter(!learner_key %in% train_ids)

baseline_model <- glm(
  all_future_on_time ~ active_days_w1_3 + mean_score_w1_3,
  data = train,
  family = binomial()
)

model_terms <- tidy(baseline_model)
model_terms

test_scored <- test |>
  mutate(
    .pred_1 = predict(
      baseline_model,
      newdata = test,
      type = "response"
    ),
    truth = factor(all_future_on_time, levels = c(0, 1)),
    estimate = factor(as.integer(.pred_1 >= 0.5), levels = c(0, 1))
  )

model_metrics <- bind_rows(
  roc_auc(test_scored, truth, .pred_1, event_level = "second"),
  accuracy(test_scored, truth, estimate),
  sens(test_scored, truth, estimate, event_level = "second"),
  spec(test_scored, truth, estimate, event_level = "second")
)

model_metrics

# 小標本のため、校正表は説明的に使う。
calibration_table <- test_scored |>
  mutate(probability_group = ntile(.pred_1, 3)) |>
  group_by(probability_group) |>
  summarise(
    learners = n(),
    mean_predicted = mean(.pred_1),
    observed_rate = mean(all_future_on_time),
    .groups = "drop"
  )

calibration_table

# 支援プロセスは、選定だけでなく到達・相談完了まで確認する。
support_process <- intervention |>
  filter(selected) |>
  group_by(study_schedule) |>
  summarise(
    selected = n(),
    contacted_rate = mean(contacted),
    reached_rate = mean(reached),
    consultation_rate = mean(consultation_completed),
    future_on_time_rate = mean(future_on_time_rate),
    .groups = "drop"
  )

support_process

# この比較は介入の因果効果を示さない。
descriptive_outcome <- intervention |>
  group_by(consultation_completed) |>
  summarise(
    learners = n(),
    mean_future_on_time_rate = mean(future_on_time_rate),
    mean_final_score = mean(final_score),
    .groups = "drop"
  )

descriptive_outcome
