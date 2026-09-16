---
name: corpus-figure
description: Answer a question about the dispatch corpus with the metric, its definition, the query behind it, the number, and what would falsify it. Runs in the calling chat: a figure is a query or two, not a sub-agent's worth of work.
when_to_use: Someone asks for a figure over the dispatch corpus — volumes, latency, word error rate, a rate by month, or a trend for department leadership.
argument-hint: [the question, and the period]
arguments: [question]
disallowed-tools: Edit, Write, NotebookEdit
---

Answer with a figure: **$question**

## Before querying

* Read `performance-metrics-analytics` for the metric's definition. If the project already defines
  it, use that definition rather than a new one; two definitions of the same word is how two
  reports disagree.
* If nothing defines it, say so and state the definition you are using before the number
  (CLAUDE.md §7.2).

## Querying

* The `cfr-postgres` MCP server logs in as a superuser behind a read-only transaction. Send
  **single SELECT statements only**, one per call, and never a statement that writes.
* Name the period and the row count the number rests on. A rate over eleven calls is a rate over
  eleven calls, and saying so is part of the answer.
* Exclude test dispatches (`is_test`) unless the question is about them, and say which you did.

## Reporting

* An unknown is reported as unknown (§6.1). A number you could not compute is not a number you
  estimate.
* State what would falsify it (§7.6): the measurement that would show this figure is wrong.

## Report

Return this and nothing else:

```
METRIC:     <the name, and what it counts>
DEFINITION: <where the definition comes from: the runbook, or stated here because nothing defines it>
QUERY:      <the SELECT that produced the number>
NUMBER:     <the figure, the period, and the rows behind it>
FALSIFIER:  <what would show it wrong>
```
