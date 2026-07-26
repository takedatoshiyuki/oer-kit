# 中級編：分析を学生支援と教育改善につなげる
# 作業ディレクトリは content/R を想定しています。

library(tidyverse)
library(broom)

learner_week <- read_csv(
  "../../assets/data/learner-week.csv",
  show_col_types = FALSE
)
intervention <- read_csv(
  "../../assets/data/intervention.csv",
  show_col_types = FALSE
)

# 第3週までに観測できる特徴だけを作る
features_week3 <- learner_week |>
  filter(week <= 3) |>
  group_by(learner_key, study_schedule, prior_lms_experience) |>
  summarise(
    events_w1_3 = sum(event_count),
    active_days_w1_3 = sum(active_days),
    on_time_w1_3 = sum(assignments_on_time),
    due_w1_3 = sum(assignments_due),
    mean_score_w1_3 = mean(avg_score),
    support_requests_w1_3 = sum(support_request),
    .groups = "drop"
  )

# 第4〜6週の提出状況を結果として定義する
future_outcome <- learner_week |>
  filter(week >= 4) |>
  group_by(learner_key) |>
  summarise(
    all_future_on_time = as.integer(all(assignments_on_time == 1)),
    future_on_time_rate = mean(assignments_on_time),
    .groups = "drop"
  )

model_data <- features_week3 |>
  left_join(future_outcome, by = "learner_key")

# 説明可能な基準モデル。個人への自動判断には使わない。
baseline_model <- glm(
  all_future_on_time ~ active_days_w1_3 + mean_score_w1_3,
  data = model_data,
  family = binomial()
)

tidy(baseline_model)

model_data <- model_data |>
  mutate(predicted_probability = predict(
    baseline_model,
    newdata = model_data,
    type = "response"
  ))

# 支援可能人数を 15 人とした場合の候補。
# 閾値は統計だけでなく、支援資源と教育方針に依存する。
support_candidates <- model_data |>
  arrange(predicted_probability, learner_key) |>
  slice_head(n = 15)

support_candidates

# 選定後のプロセスを確認する
intervention |>
  filter(selected) |>
  summarise(
    selected = n(),
    contacted = sum(contacted),
    reached = sum(reached),
    consultation_completed = sum(consultation_completed)
  )

# 「誰を選んだか」だけでなく「誰に支援が届いたか」を確認する
intervention |>
  filter(selected) |>
  group_by(study_schedule) |>
  summarise(
    selected = n(),
    reach_rate = mean(reached),
    completion_rate = mean(consultation_completed),
    future_on_time_rate = mean(future_on_time_rate),
    .groups = "drop"
  )

# 比較は記述的。ランダム割付ではないため因果効果とは解釈しない。
intervention |>
  group_by(consultation_completed) |>
  summarise(
    learners = n(),
    mean_future_on_time_rate = mean(future_on_time_rate),
    mean_final_score = mean(final_score),
    .groups = "drop"
  )
