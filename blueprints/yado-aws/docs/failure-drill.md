# Failure drill: the SSO outage

Status: **designed, not executed** (the stack has not been deployed).

## Why this drill

In October 2026 the three SSO containers on the homelab were found in
`Exited (255)` after roughly two weeks. They had no restart policy, so they did
not come back after the host restarted. Nothing alerted. Every app that signs
in through SSO was affected.

The root cause was not fully proven, but the failure mode is clear: a service
stopped, and nobody was told. The drill checks that this design catches and
repairs it.

## What the design does about it

| Layer | Behaviour |
|---|---|
| ECS service scheduler | Replaces a stopped or failed task automatically; the desired count is enforced continuously |
| ALB health check | Stops sending traffic to an unhealthy target and starts the replacement only when it passes |
| Deployment circuit breaker | A bad new version rolls back instead of leaving the service down |
| `service_down` alarm | `RunningTaskCount` below 1 for two minutes. Missing data counts as breaching, so a vanished service alarms rather than going quiet |
| `unhealthy_targets` and `alb_5xx` alarms | Catch a running but broken service |
| SNS | Delivers the alarm by email |

## Procedure

Run against a real deployment, never production traffic you care about.

1. Confirm the dashboard shows one running task for `sso` and the target group
   is healthy.
2. Stop the task: `aws ecs stop-task --cluster yado --task <arn>`.
3. Record the time, then watch the service events and the dashboard.

## Expected result

- ECS starts a replacement task without intervention.
- The `service_down` alarm may briefly enter ALARM; the notification arrives
  and then recovers.
- `https://sso.<domain>/health` returns 200 again.
- Login through the launcher works after recovery.

## Pass criteria

- Time from stop to healthy replacement is recorded.
- An alert was actually received at the configured email.
- No manual action was needed to restore service.

## Second scenario: a bad deploy

Push an image tag whose container fails its health check. Expected: the
deployment circuit breaker rolls back to the last working task definition and
the service never goes fully down. Record the time to roll back.

## What to put here after a real run

Measured recovery times, a screenshot of the alarm notification, and one thing
that did not work as predicted. A drill that confirms everything is a weaker
result than one that finds something.
