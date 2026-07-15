// agent-alerts.bicep
// Four Azure Monitor scheduled query alert rules for the Foundry agent
// operating profile.
//
// Alert categories (one resource each):
//   failure       — 5xx / failed-request signal (AppRequests)
//   latency       — p95 dependency / tool-call latency (AppDependencies)
//   token_cost    — token-usage budget threshold (AppMetrics gen_ai.*)
//   quality_safety — eval pass-rate drift, 8-day baseline (AppMetrics)
//
// API version: Microsoft.Insights/scheduledQueryRules@2023-12-01
//
// Wiring contract
//   telemetryScopeResourceId : ARM ID of the workspace-based App Insights
//                              component (or Log Analytics Workspace).
//   actionGroupResourceId    : ARM ID of an EXISTING action group.
//                              This module NEVER creates an action group.
//
// The quality_safety alert embeds the eval-quality-drift KQL inline
// (semantically identical to references/queries/eval-quality-drift.kql).
// The agt-denial-rate.kql file ships as an operator/governance reference
// query; it is NOT a fifth alert resource.
//
// All four alert resources reference the same action group and the same
// telemetry scope.

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Region. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Shared prefix for all four alert rule names (e.g. "agent" → "agent-failure").')
param alertNamePrefix string = 'agent'

@description('ARM resource ID of the telemetry scope (workspace-based App Insights or Log Analytics Workspace).')
param telemetryScopeResourceId string

@description('ARM resource ID of an EXISTING Azure Monitor action group. Do NOT create one in this module.')
param actionGroupResourceId string

@description('Enable or disable all four alert rules on deployment.')
param enabled bool = true

@description('Alert severity applied to all four rules: 0=Critical, 1=Error, 2=Warning, 3=Informational, 4=Verbose.')
@minValue(0)
@maxValue(4)
param severity int = 2

@description('Evaluation frequency for failure / latency / token_cost alerts (ISO 8601 duration).')
@allowed(['PT1M', 'PT5M', 'PT15M', 'PT30M', 'PT1H'])
param evaluationFrequency string = 'PT5M'

@description('Query window size for failure / latency / token_cost alerts (ISO 8601 duration).')
@allowed(['PT5M', 'PT15M', 'PT30M', 'PT1H', 'PT6H', 'P1D'])
param windowSize string = 'PT15M'

// Per-alert thresholds -------------------------------------------------------

@description('Failure alert: alert when failed-request count exceeds this value per window (0 = any failure).')
@minValue(0)
param failureCountThreshold int = 0

@description('Latency alert: alert when the p95 dependency call duration (ms) exceeds this value.')
@minValue(100)
param latencyP95ThresholdMs int = 3000

@description('''Token-cost alert: alert when total token count per evaluation window exceeds this.
Assumption: tokens are emitted as AppMetrics with Name in
  { "gen_ai.client.token.usage", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens" }
and Sum = token count.''')
@minValue(1)
param tokenBudgetThreshold int = 100000

// Quality / safety alert has a long window to capture the 8-day baseline ----

@description('Evaluation frequency for the quality_safety alert (ISO 8601 duration).')
@allowed(['PT15M', 'PT30M', 'PT1H', 'PT6H'])
param qualityEvaluationFrequency string = 'PT1H'

@description('Query window size for the quality_safety alert — must cover the full 8-day baseline lookback (ISO 8601 duration).')
@allowed(['P9D', 'P14D', 'P30D'])
param qualityWindowSize string = 'P9D'

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

var scopes       = [telemetryScopeResourceId]
var actionGroups = [actionGroupResourceId]

// All four rules use the same single-evaluation-period failing-period block.
var fp = {
  minFailingPeriodsToAlert: 1
  numberOfEvaluationPeriods: 1
}

// KQL query strings ---------------------------------------------------------
// All queries target workspace-based App Insights tables (AppRequests,
// AppDependencies, AppMetrics).  No user-supplied input is interpolated
// into query strings — all parameters flow through the numeric threshold/
// operator fields of the criteria block.

// failure: count failed requests; alert when count > failureCountThreshold.
var kqlFailure = '''AppRequests
| where Success == false'''

// latency: compute p95 dependency duration; use metricMeasureColumn so the
// alert engine compares the p95 value directly against latencyP95ThresholdMs.
// Empty window → percentile returns null → comparison false → no alert.
var kqlLatency = '''AppDependencies
| summarize p95_ms = percentile(DurationMs, 95)'''

// token_cost: sum token metrics across the window; alert when total exceeds
// tokenBudgetThreshold.  Empty window → sum returns 0 → 0 < threshold → no alert.
// @minValue(1) on tokenBudgetThreshold prevents false alerts on zero-traffic windows.
var kqlTokenCost = '''AppMetrics
| where Name in ('gen_ai.client.token.usage', 'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens')
| summarize total_tokens = sum(Sum)'''

// quality_safety: eval pass-rate drift vs 8-day rolling baseline.
// Semantically identical to references/queries/eval-quality-drift.kql.
// range sentinel creates exactly one row; isfinite() drops null deltas
// (missing recent or baseline data) so absent metrics do not false-alert.
// Threshold (-0.05 = -5 pp) is embedded as a KQL let-variable.
var kqlQualitySafety = '''let pass_rate_delta_threshold = -0.05;
let recent_pass_rate = toscalar(
    AppMetrics
    | where TimeGenerated > ago(1h)
    | where Name == 'agent_eval.pass_rate'
    | where Count > 0
    | summarize sum(Sum) / sum(Count)
);
let baseline_pass_rate = toscalar(
    AppMetrics
    | where TimeGenerated between (ago(8d) .. ago(1d))
    | where Name == 'agent_eval.pass_rate'
    | where Count > 0
    | summarize sum(Sum) / sum(Count)
);
range sentinel from 1 to 1 step 1
| extend
    recent   = recent_pass_rate,
    baseline = baseline_pass_rate,
    delta    = (recent_pass_rate - baseline_pass_rate)
| where isfinite(recent) and isfinite(baseline)
| where delta <= pass_rate_delta_threshold
| project recent, baseline, delta'''

// ---------------------------------------------------------------------------
// Alert resources
// ---------------------------------------------------------------------------

// 1. failure ─────────────────────────────────────────────────────────────────
resource alertFailure 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertNamePrefix}-failure'
  location: location
  properties: {
    description: 'Fires when AppRequests contains failed (Success == false) requests in the evaluation window.'
    enabled: enabled
    scopes: scopes
    evaluationFrequency: evaluationFrequency
    windowSize: windowSize
    severity: severity
    criteria: {
      allOf: [
        {
          query: kqlFailure
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: failureCountThreshold
          failingPeriods: fp
        }
      ]
    }
    actions: {
      actionGroups: actionGroups
    }
  }
}

// 2. latency ──────────────────────────────────────────────────────────────────
resource alertLatency 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertNamePrefix}-latency'
  location: location
  properties: {
    description: 'Fires when the p95 dependency (tool call) duration exceeds latencyP95ThresholdMs milliseconds.'
    enabled: enabled
    scopes: scopes
    evaluationFrequency: evaluationFrequency
    windowSize: windowSize
    severity: severity
    criteria: {
      allOf: [
        {
          query: kqlLatency
          metricMeasureColumn: 'p95_ms'
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: latencyP95ThresholdMs
          failingPeriods: fp
        }
      ]
    }
    actions: {
      actionGroups: actionGroups
    }
  }
}

// 3. token_cost ───────────────────────────────────────────────────────────────
resource alertTokenCost 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertNamePrefix}-token-cost'
  location: location
  properties: {
    description: 'Fires when total token usage (gen_ai.*) exceeds tokenBudgetThreshold in the evaluation window.'
    enabled: enabled
    scopes: scopes
    evaluationFrequency: evaluationFrequency
    windowSize: windowSize
    severity: severity
    criteria: {
      allOf: [
        {
          query: kqlTokenCost
          metricMeasureColumn: 'total_tokens'
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: tokenBudgetThreshold
          failingPeriods: fp
        }
      ]
    }
    actions: {
      actionGroups: actionGroups
    }
  }
}

// 4. quality_safety ───────────────────────────────────────────────────────────
resource alertQualitySafety 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertNamePrefix}-quality-safety'
  location: location
  properties: {
    description: 'Fires when the recent 1-hour agent_eval.pass_rate falls >= 5 pp below the 8-day rolling baseline.'
    enabled: enabled
    scopes: scopes
    evaluationFrequency: qualityEvaluationFrequency
    windowSize: qualityWindowSize
    severity: severity
    criteria: {
      allOf: [
        {
          query: kqlQualitySafety
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: fp
        }
      ]
    }
    actions: {
      actionGroups: actionGroups
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs — resource IDs and names; no secrets exposed
// ---------------------------------------------------------------------------

@description('ARM resource ID of the failure alert rule.')
output failureAlertId string = alertFailure.id

@description('Name of the failure alert rule.')
output failureAlertName string = alertFailure.name

@description('ARM resource ID of the latency alert rule.')
output latencyAlertId string = alertLatency.id

@description('Name of the latency alert rule.')
output latencyAlertName string = alertLatency.name

@description('ARM resource ID of the token-cost alert rule.')
output tokenCostAlertId string = alertTokenCost.id

@description('Name of the token-cost alert rule.')
output tokenCostAlertName string = alertTokenCost.name

@description('ARM resource ID of the quality/safety alert rule.')
output qualitySafetyAlertId string = alertQualitySafety.id

@description('Name of the quality/safety alert rule.')
output qualitySafetyAlertName string = alertQualitySafety.name
