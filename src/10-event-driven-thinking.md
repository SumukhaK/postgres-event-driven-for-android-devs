---
title: Event-driven thinking: tell the world what happened
part: Part 3 · Event-driven backend
summary: Why the request should not do everything itself, what an event is, and the problem we must solve first.
---

**An event is a short record of something that already happened, such as "order 7 was placed". Other parts of the system react to it, so the code that placed the order does not need to know about them.**

In this chapter, we will learn:

- What goes wrong when one request does every job itself
- What an event is, and how it differs from a command
- The event-driven idea in Android terms
- What an event should contain
- The hidden problem in "save, then notify", which the next chapter solves

Let's get started.

## The request that does everything

Our order endpoint from chapter 9 saves the order and takes stock. Now the product people ask for more. When an order is placed, we must also:

- send a confirmation email,
- print a ticket in the kitchen,
- add loyalty points,
- tell the analytics team.

The first idea is to add these steps to the endpoint, one after another:

```python
def create_order(...):
    result = place_order(conn, ...)     # save the order
    send_email(result)                  # 1 second, sometimes fails
    print_kitchen_ticket(result)
    add_loyalty_points(result)
    notify_analytics(result)
    return result
```

This works on day one. Then it hurts: every new feature changes the order code, the customer waits for all steps, and a failure in one step affects the others. Let's see the failure part with a real experiment.

## What actually breaks: a real experiment

I added one step, "send email", to the order code from chapter 9. The email service is simulated: it takes one second, and I can switch it to "down". Everything else is the real code and the real database. I tried the email in two places: **inside** the transaction, and **after** the commit. (The script is `demos/ch10_coupling.py`.)

```text
A. email INSIDE the transaction   email up   -> request OK                       took 1.0s | orders saved: 1 | stock: 198
A. email INSIDE the transaction   email down -> request FAILED (email down)      took 1.0s | orders saved: 0 | stock: 200
B. email AFTER the commit         email up   -> request OK                       took 1.0s | orders saved: 1 | stock: 198
B. email AFTER the commit         email down -> request FAILED (email down)      took 1.0s | orders saved: 1 | stock: 198
```

Read the four lines slowly. Every request took a full second, even though saving the order is fast, because the customer waits for the email. And look at the two failures:

- **A, email inside the transaction, email down:** the order was **not saved** (0 orders, stock back to 200). A broken email service stopped us from selling chai. Worse, while we waited the one second, our transaction was holding the row lock on the product (chapter 8), so other customers buying the same item had to wait too.
- **B, email after the commit, email down:** the order **was saved** (stock is 198), but the customer got an error. They will probably tap "Order" again, and now we have two orders. The email was never sent, and nobody knows.

Neither version is right. Both are what you get when one request tries to change two different systems: our database and the email service. We will come back to this at the end of the chapter, because it is the central problem of Part 3.

## The idea: announce what happened

Instead of calling every service, the order code does only its own job, and then **announces a fact**:

> OrderPlaced: order 7, customer 1, total ₹55.

Anyone who cares can listen, and react in their own time. The email service sends an email. The kitchen service prints a ticket. The order code does not know who they are, and does not wait for them.

```flow
{"width":720,"height":290,"intro":"Before: the order code calls everyone. After: it announces, and listeners react.",
 "nodes":[
  {"id":"o","label":"Order service","sub":"saves the order","x":10,"y":115,"kind":"app","w":150},
  {"id":"e","label":"Event","sub":"OrderPlaced #7","x":260,"y":115,"kind":"queue","w":150},
  {"id":"m","label":"Email","x":520,"y":10,"w":120},
  {"id":"k","label":"Kitchen","x":520,"y":100,"w":120},
  {"id":"l","label":"Loyalty","x":520,"y":190,"w":120},
  {"id":"a","label":"Analytics","x":520,"y":250,"w":120}],
 "edges":[{"from":"o","to":"e","label":"announce"},{"from":"e","to":"m"},{"from":"e","to":"k"},{"from":"e","to":"l"},{"from":"e","to":"a"}],
 "steps":[
  {"nodes":["o"],"text":"The order service does its own job: save the order, take the stock."},
  {"edges":[0],"nodes":["e"],"labels":["OrderPlaced"],"text":"Then it records one fact: an order was placed. It does not call anyone."},
  {"edges":[1,2],"nodes":["m","k"],"labels":["react","react"],"text":"The email and kitchen services each notice the event and react, on their own."},
  {"edges":[3,4],"nodes":["l","a"],"labels":["react","react"],"text":"Next month, someone adds a loyalty service and analytics. They just listen. The order code does not change at all."}]}
```

This is called **event notification**. Martin Fowler describes it as: "a system sends event messages to notify other systems of a change in its domain", and says it is nice because "it implies a low level of coupling, and is pretty simple to set up."

!!! android "Android parallel"
    You already use this idea, in memory, inside one app. Android's own documentation says apps "send and receive broadcast messages ... similar to the publish-subscribe design pattern", where "the system and apps typically send broadcasts when certain events occur". A `BroadcastReceiver` is a listener. And a Kotlin `SharedFlow` is, in its documentation's words, a hot flow that "shares emitted values among all its collectors in a broadcast fashion, so that all collectors get all emitted values". The sender does not know who collects. That is what we are building, on the server.

The big difference is **durability**. A `SharedFlow` lives in your app's memory. If the process dies, the values are gone, and for UI events that is fine. A server event like "order placed" is business data: if it is lost, an email is never sent. So our events must be **stored**, and that is why this course builds them on Postgres.

## Event, command, query: do not mix them up

Three kinds of messages look alike and behave differently. This is the convention we use in this course:

| Kind | Sounds like | Example | Who decides? |
|---|---|---|---|
| **Command** | an order, present tense | `SendEmail` | The sender wants one specific thing to happen. It can be refused. |
| **Event** | a fact, past tense | `OrderPlaced` | It already happened. Listeners cannot refuse it. |
| **Query** | a question | `GetOrder` | The sender wants data back. |

An event is named in the **past tense**, because it cannot be undone or argued with. If your event is called `SendEmail`, it is really a command wearing a costume, and you have coupled the order code to the email service again.

## What goes inside an event

Keep an event small and boring. Ours will have:

```json
{
  "event_id": 1042,
  "type": "OrderPlaced",
  "occurred_at": "2026-11-13T10:15:00Z",
  "payload": { "order_id": 7, "customer_id": 1, "total": "55.00" }
}
```

- **`event_id`** is unique. Listeners use it to notice duplicates (chapter 12).
- **`type`** says what happened.
- **`occurred_at`** is when it happened.
- **`payload`** is the data a listener needs. Ids and the key facts, not whole tables. A listener that needs more can ask for it.

Notice that the total is a string, `"55.00"`, as we warned in chapter 9. And in Postgres, this payload fits in a `jsonb` column, the type we met in chapter 2.

## The price of loose coupling

Event notification is not free. Fowler warns about the other side in the same article: "It can become problematic, however, if there really is a logical flow that runs over various event notifications. The problem is that it can be hard to see such a flow as it's not explicit in any program text. Often the only way to figure out this flow is from monitoring a live system."

In practice, when something goes wrong ("why did the customer get no email?"), you can no longer read one function top to bottom. You need to follow the event. This is why this course adds **logging and an `events` table you can query**: if events are rows, you can look at them with the SQL you already know.

## The hidden problem: two places to write

Go back to the experiment. Even with events, the order service must do two things:

1. save the order in the database, and
2. announce `OrderPlaced`.

If the announcement goes to something **outside** the database, like a message queue or an email service, then these are two separate systems, and no single transaction covers both. Whichever you do first, a crash between them leaves you in a bad state:

- save first, announce second, crash in the middle: the order exists, **no one is told**.
- announce first, save second, crash in the middle: everyone is told about an order that **does not exist**.

This is exactly what the experiment's lines A and B showed. It is known as the **dual-write problem**. The good news: there is a clean fix that uses the tool you already trust, the Postgres transaction. Write the event into **a table, in the same transaction as the order**. Either both rows are saved, or neither. A separate worker then reads that table and delivers the events. That is the **outbox pattern**, the next chapter.

```flow
{"width":720,"height":210,"intro":"The plan for Part 3.",
 "nodes":[
  {"id":"api","label":"API","sub":"order + event, one transaction","x":10,"y":70,"kind":"app","w":210},
  {"id":"db","label":"PostgreSQL","sub":"orders + outbox table","x":290,"y":70,"kind":"db","w":170},
  {"id":"w","label":"Worker","sub":"reads the outbox","x":540,"y":10,"kind":"queue","w":150},
  {"id":"c","label":"Consumers","sub":"email, kitchen, ...","x":540,"y":130,"w":150}],
 "edges":[{"from":"api","to":"db","label":"one COMMIT"},{"from":"db","to":"w","label":"read events"},{"from":"w","to":"c","label":"deliver"}],
 "steps":[
  {"edges":[0],"nodes":["api","db"],"labels":["both"],"text":"Chapter 11: the order and its event are written in the same transaction. They live or die together."},
  {"edges":[1],"nodes":["w"],"labels":["poll"],"text":"Chapter 12: a worker picks up new events from the table, safely, even with several workers."},
  {"edges":[2],"nodes":["c"],"labels":["deliver"],"text":"Consumers do the slow jobs. If one fails, it is retried. The order is already safe."}]}
```

## Summary

- A request that does every job itself is slow, tightly coupled, and has no good answer when one step fails. I measured it: every request took the full second of a slow email, and a failed email either lost the order or sent the customer an error after the order was saved.
- An **event** is a past-tense fact (`OrderPlaced`) that other parts react to. The sender does not know the listeners.
- In Android terms: broadcasts and `SharedFlow`, but durable, because on a server a lost event is lost business.
- An event has an id, a type, a time, and a small payload.
- The cost: the flow is no longer visible in one place, so you need good logs and queryable event data.
- Writing to the database and to another system cannot be one transaction. The fix, the outbox, comes next.

!!! faq "Is event-driven the same as microservices?"
    No. You can have events inside one application with one database, which is exactly what we build. Microservices often use events, but you do not need microservices to use events.

!!! faq "Do I need Kafka or RabbitMQ?"
    Not to learn the ideas, and not for many small and medium systems. We use only Postgres in this course, so every piece is visible and testable. In the last chapter we talk about when a dedicated broker makes sense.

## Sources

- [Martin Fowler: What do you mean by "Event-Driven"?](https://martinfowler.com/articles/201701-event-driven.html)
- [Android Developers: Broadcasts overview](https://developer.android.com/develop/background-work/background-tasks/broadcasts)
- [Kotlin coroutines API: SharedFlow](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/-shared-flow/)
- The experiment: `demos/ch10_coupling.py` in the course repository. The email service in it is simulated, and everything else is real.

That's it for now. In the next chapter, we will build the outbox, step by step.
