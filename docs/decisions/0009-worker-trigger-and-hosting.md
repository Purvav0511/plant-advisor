# 0009: Worker trigger, and Cloud Run now with a portable path to AWS

**Context:** the owner may end up on AWS (Lambda + SQS or ECS) and asked whether daily volume decides it. On Cloud Run, CPU is throttled after a response is sent, so a "fire-and-forget after responding" kick may never go out.

**Decision**
- The API sends the `/drain` kick **before** returning (short timeout, errors swallowed); the worker processes inside that request. The scheduler pings `/drain` **every minute**, not every 5.
- Every service is a plain Docker image. The queue sits behind a `Queue` interface (`pgmq` now, an SQS adapter later), and `/drain`'s core is a plain function that a Lambda handler could call.
- Deploy to **Cloud Run** for the MVP; decide AWS at PLAN 7.3.

**Why volume doesn't decide it yet:** Cloud Run's monthly free tier is 180k vCPU-seconds, 360k GiB-seconds and 2M requests. *Assuming* (not measured) ~60 s per analysis on 1 vCPU / 2 GiB, that covers ~3,000 analyses a month (~100/day) for free, then per-second billing. Lambda and SQS free tiers are similar in scale. At hundreds or low thousands of requests a day, either platform is trivial; the model API cost dominates. Choose AWS when the company's infrastructure, compliance or existing account requires it, not for capacity. Re-check with measured per-request time at 7.1 and current free-tier terms before the pilot.

**Alternatives:** Lambda for the worker now (PyTorch cold starts, 15-minute limit; workable but slower); ECS Fargate (no free tier).
