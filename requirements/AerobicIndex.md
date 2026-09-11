Implement an **Aerobic Base Dashboard** in the existing FitnessDashboard project.

## Objective

Create a dashboard that evaluates whether my training is developing my aerobic base.

Garmin Training Status appears heavily influenced by intensity, EPOC and short-term VO₂-max changes. This dashboard should instead emphasize:

* sustainable low-intensity training volume;
* consistency and frequency;
* long-session durability;
* intensity discipline;
* aerobic efficiency;
* cardiac drift;
* recovery and the ability to absorb training.

The result should be a transparent weekly score from 0–100. Every score must be explainable from the underlying data.

Do not use Garmin Training Status, Training Load, Training Effect or EPOC as inputs to the score. They may be displayed separately for comparison.

## Repository-first instructions

Before implementing:

1. Inspect the repository structure, build system, frontend framework, backend framework, database and existing Garmin import code.
2. Reuse existing architectural patterns, components, naming conventions and chart libraries.
3. Do not introduce a second framework or unnecessary dependencies.
4. Identify which required Garmin fields are already available.
5. Do not invent Garmin API fields or endpoints. When data is unavailable, represent the metric as unavailable and continue with the metrics that can be calculated.
6. Keep scoring logic in a deterministic, independently testable domain service rather than inside UI components.
7. Use the Europe/Bucharest timezone and Monday–Sunday ISO weeks.

## Configurable settings

Add configuration for:

* weekly aerobic-base-minute target, default: 360 minutes;
* qualifying-session minimum, default: 30 minutes;
* long-session target, default: 120 minutes;
* primary aerobic sport, default: cycling or automatically choose the sport contributing the most aerobic-base minutes;
* eligible activity types;
* excluded activity types;
* heart-rate-zone boundaries;
* optional LT1 heart-rate boundary;
* planned weekly targets, including planned deload weeks;
* warm-up trimming, default: 10 minutes;
* cooldown trimming, default: 5 minutes;
* minimum duration for cardiac-drift analysis, default: 60 minutes.

Strength training must not count toward aerobic-base minutes.

Walking should count only when it is configured as an eligible aerobic activity and contains meaningful heart-rate data.

## Required Garmin data

Use the existing Garmin ingestion layer where possible.

### Activity summary

Useful fields include:

* activity ID;
* activity type;
* start time;
* elapsed and moving duration;
* distance;
* average and maximum heart rate;
* time in heart-rate zones;
* average and normalized power, when available;
* speed or pace;
* elevation gain;
* indoor/outdoor status.

### Activity samples

When available:

* timestamp;
* heart rate;
* power;
* speed or pace;
* cadence;
* altitude;
* moving state.

Prefer sample-level calculation. Fall back to Garmin-provided zone durations when samples are unavailable.

### Daily wellness

When available:

* resting heart rate;
* overnight HRV or Garmin HRV summary;
* sleep duration;
* sleep score;
* Body Battery;
* Training Readiness.

Missing wellness metrics must not automatically produce zero points.

## Weekly score

The score consists of eight components.

### 1. Low-intensity volume: 30 points

Define:

ABM = Zone 2 minutes + 0.5 × Zone 1 minutes

Only include eligible endurance activities.

Score:

volumeScore = 30 × min(ABM / weeklyTargetABM, 1)

Do not award extra points above the weekly target. Show excess volume separately.

Display:

* Zone 1 minutes;
* Zone 2 minutes;
* total ABM;
* target ABM;
* target-completion percentage.

### 2. Frequency: 10 points

A qualifying day contains at least the configured minimum number of aerobic-base minutes.

Score:

frequencyScore = min(2 × qualifyingDays, 10)

Five qualifying days receive the maximum score. Do not reward seven training days more than five.

### 3. Long-session stimulus: 10 points

Find the longest eligible session based on low-intensity minutes, not merely total elapsed duration.

Score:

longSessionScore = 10 × min(longestSessionBaseMinutes / longSessionTarget, 1)

The target must be configurable.

### 4. Intensity discipline: 10 points

Calculate:

easyProportion = minutes below LT1 / total eligible endurance minutes

When LT1 is unavailable, use configured low-intensity heart-rate zones.

Scoring:

* 80% or more: 10 points
* 70% to less than 80%: 8 points
* 60% to less than 70%: 5 points
* less than 60%: 0 points

Do not include strength-training time in the denominator.

### 5. Plan adherence and progression: 10 points

Compare actual ABM against the target configured for that specific week.

Scoring based on actual divided by planned:

* 90–110%: 10 points
* 75–90% or 110–120%: 7 points
* 60–75% or 120–130%: 3 points
* outside those ranges: 0 points

A planned deload week can receive the full score when completed as planned.

If no week-specific target exists, use the default weekly target and clearly label the result as based on the default target.

### 6. Aerobic durability/cardiac drift: 10 points

Use Pa:Hr-style decoupling on qualifying steady aerobic sessions.

Eligibility:

* duration of at least 60 minutes;
* at least 80% of the session below LT1;
* sufficient heart-rate coverage;
* sufficient power coverage for power-based calculation;
* exclude stopped periods;
* trim the configured warm-up and cooldown;
* split the remaining session into equal-duration halves.

For cycling with power:

efficiencyFactor = averagePower / averageHeartRate

For running, or cycling without power:

efficiencyProxy = averageSpeed / averageHeartRate

Never combine power-based and speed-based values in the same trend.

Calculate:

decouplingPercent =
100 × (firstHalfEfficiency − secondHalfEfficiency) / firstHalfEfficiency

Scoring:

* 3% or less: 10 points
* greater than 3% through 5%: 8 points
* greater than 5% through 7.5%: 5 points
* greater than 7.5% through 10%: 2 points
* greater than 10%: 0 points

Negative decoupling should receive full points but still display the raw value.

For the weekly score, use the median of qualifying sessions. Also show every qualifying session individually.

Assign a confidence level:

* High: power-based, at least 90 minutes, excellent sensor coverage, stable conditions or indoor ride.
* Medium: power-based outdoor session of at least 60 minutes.
* Low: speed-based proxy, variable terrain, poor coverage or other significant confounders.

Do not silently treat a speed-based proxy as equivalent to a power-based calculation.

### 7. Aerobic-efficiency trend: 10 points

Calculate sport-specific aerobic efficiency:

* cycling with power: power divided by heart rate;
* running: speed divided by heart rate;
* cycling without power: speed divided by heart rate, marked as a proxy.

Use only qualifying low-intensity sections.

Compare the median from the most recent 28 days with the median from the preceding 28 days:

changePercent =
100 × (recentMedian − previousMedian) / previousMedian

Scoring:

* improvement of at least 3%: 10 points
* improvement of 1% to less than 3%: 8 points
* between −1% and +1%: 6 points
* decline of 1% to 3%: 3 points
* decline greater than 3%: 0 points

Do not combine different sports or different efficiency units.

Show sample count and confidence. Require a configurable minimum sample count before scoring the trend.

### 8. Recovery and absorption: 10 points

Use available Garmin recovery metrics:

* HRV trend;
* resting-heart-rate trend;
* sleep-duration trend;
* morning Body Battery or another consistently available Garmin recovery metric.

Each available metric contributes an equal portion of the 10 points.

Suggested thresholds:

#### HRV

Compare the seven-day median with the established 28-day baseline:

* at least 90% of baseline: full points;
* 80–90%: half points;
* below 80%: zero.

#### Resting heart rate

Compare the seven-day mean with the established baseline:

* no more than 3 bpm above baseline: full points;
* 3–5 bpm above baseline: half points;
* more than 5 bpm above baseline: zero.

#### Sleep

Compare the seven-day average with the configured sleep goal or established baseline:

* at least 90%: full points;
* 80–90%: half points;
* below 80%: zero.

#### Body Battery or equivalent

Compare the seven-day morning average with its 28-day baseline:

* at least 90%: full points;
* 75–90%: half points;
* below 75%: zero.

If only two of four recovery metrics are available, calculate the recovery score from those two and report reduced data coverage. Do not treat missing metrics as zero.

## Missing-data behaviour

Each component must expose:

* earned points;
* maximum possible points;
* availability;
* confidence;
* raw inputs;
* explanatory text.

Calculate:

availablePoints = sum of maximum points for available components

normalizedScore = 100 × earnedPoints / availablePoints

dataCoverage = availablePoints / 100

Display both:

* Aerobic Base Score: normalized score;
* Data coverage: percentage.

Example:

* Aerobic Base Score: 84/100
* Data coverage: 80%
* Missing: power-based cardiac drift and Body Battery

Do not hide missing-data limitations.

## Status labels

Use:

* 90–100: Strong base-building week
* 75–89: Productive aerobic development
* 60–74: Adequate aerobic stimulus
* 45–59: Mostly maintenance
* below 45: Insufficient stimulus or poor absorption

The status explanation should identify the strongest and weakest components.

Example:

“Volume and consistency were strong, but cardiac drift increased and recovery was below baseline.”

## Dashboard layout

### Header controls

Include:

* week selector;
* previous/next week;
* 4-, 12-, 26- and 52-week range selector;
* sport selector;
* settings link or panel;
* refresh/import status.

### Weekly summary cards

Show:

* Aerobic Base Score;
* status label;
* data coverage;
* ABM versus target;
* longest easy session;
* cardiac drift;
* recovery score.

### Component breakdown

Show all eight components as horizontal progress bars or compact cards:

* component name;
* earned points;
* maximum points;
* raw metric;
* confidence;
* explanation;
* link to relevant activities.

### Required graphs

#### 1. Aerobic Base Score trend

Line chart by week.

Include:

* normalized score;
* data-coverage indicator;
* optional Garmin Training Status annotation for comparison.

#### 2. Score-component breakdown

Stacked weekly bars for:

* volume;
* frequency;
* long session;
* intensity discipline;
* plan adherence;
* durability;
* efficiency;
* recovery.

#### 3. Weekly aerobic volume

Stacked bars showing:

* Zone 1 minutes;
* Zone 2 minutes;
* weekly target line;
* total ABM.

#### 4. Intensity distribution

Weekly percentage distribution for heart-rate zones.

Clearly distinguish eligible endurance training from all recorded activities.

#### 5. Long-session progression

Line chart of the longest weekly low-intensity session.

#### 6. Cardiac-drift trend

Plot qualifying sessions over time:

* decoupling percentage;
* sport;
* duration;
* power-based versus proxy;
* confidence;
* target reference line at 5%.

Allow opening the underlying activity.

#### 7. Aerobic-efficiency trend

Separate series or separate views by sport and measurement type.

Do not mix:

* cycling watts/heart rate;
* cycling speed/heart rate;
* running speed/heart rate.

Include the rolling 28-day median.

#### 8. Recovery trends

Display synchronized trends for:

* HRV;
* resting heart rate;
* sleep;
* Body Battery or equivalent.

Show personal baselines rather than population norms.

### Activity table

Provide a drill-down table with:

* date;
* activity type;
* duration;
* Zone 1 minutes;
* Zone 2 minutes;
* ABM;
* easy percentage;
* average heart rate;
* average power or speed;
* cardiac drift;
* confidence;
* data-quality warnings.

## Explanations and recommendations

Generate a short deterministic weekly explanation from component results.

Examples:

* “You reached 82% of the weekly aerobic-volume target.”
* “Only two days contained at least 30 aerobic-base minutes.”
* “Your longest easy session increased from 90 to 112 minutes.”
* “Cardiac drift was 6.1%, suggesting limited durability at this duration or intensity.”
* “Aerobic efficiency improved by 2.4% compared with the previous 28-day period.”
* “Recovery metrics were below baseline; avoid increasing volume solely to improve the score.”

Recommendations should be based on the weakest actionable component. Do not recommend extra intensity merely to raise the score.

## Suggested domain model

Adapt this to the project’s existing conventions:

* AerobicBaseSettings
* WeeklyAerobicTarget
* AerobicBaseWeek
* AerobicBaseScore
* ComponentScore
* AerobicBaseActivityMetrics
* CardiacDriftResult
* AerobicEfficiencyResult
* RecoveryMetricResult
* DataConfidence
* DataQualityWarning

A component result should contain approximately:

* component identifier;
* earned points;
* maximum points;
* availability;
* confidence;
* raw value;
* display unit;
* explanation;
* contributing activity IDs;
* warnings.

## Implementation requirements

* Keep formulas in pure functions.
* Make thresholds configurable.
* Store enough derived data to reproduce historical scores.
* Avoid recalculating every raw sample during every page load.
* Make recalculation idempotent.
* Preserve source-data provenance.
* Avoid double-counting duplicate Garmin activities.
* Assign an activity to a week using its local start time.
* Handle activities crossing midnight.
* Exclude stopped time from sample-based calculations.
* Validate sensor coverage before calculating drift or efficiency.
* Clearly distinguish zero from unavailable.
* Make the UI usable in both light and dark mode.
* Ensure graphs work on desktop and narrow screens.

## Tests

Add unit tests covering:

* every scoring boundary;
* ABM calculation;
* weekly timezone boundaries;
* activities crossing midnight;
* missing heart-rate samples;
* missing power;
* strength-training exclusion;
* frequency counting only once per day;
* planned deload weeks;
* negative cardiac drift;
* cardiac drift greater than 10%;
* missing recovery fields;
* normalized score and data coverage;
* separation of sport-specific efficiency units;
* duplicate Garmin activities;
* incomplete sensor coverage.

Add integration or component tests appropriate to the existing project.

## Example weekly result

Use an example similar to this in tests or development fixtures:

* ABM: 375
* weekly target: 360
* qualifying days: 5
* longest easy session: 120 minutes
* easy proportion: 88%
* plan completion: 104%
* median cardiac drift: 4.2%
* aerobic-efficiency change: +1.5%
* recovery: three of four metrics normal

Expected component scores:

* volume: 30
* frequency: 10
* long session: 10
* intensity discipline: 10
* plan adherence: 10
* durability: 8
* efficiency: 8
* recovery: approximately 7.5

Expected total with full availability:

93.5/100 — Strong base-building week

## Definition of done

The feature is complete when:

1. Garmin-derived activities can be aggregated into ISO weeks.
2. The score is calculated by a tested backend/domain service.
3. Missing data and confidence are visible.
4. The dashboard displays the weekly summary and all required graphs.
5. Every component can be traced to its raw inputs.
6. Historical weeks can be recalculated.
7. Thresholds and targets can be configured.
8. Existing FitnessDashboard functionality and tests continue to work.

Start by inspecting the repository and producing a concise implementation plan. Then implement the feature using the project’s existing architecture. Do not stop after producing mockups or pseudocode.
