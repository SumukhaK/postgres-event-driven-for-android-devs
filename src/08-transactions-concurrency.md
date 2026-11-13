---
title: Transactions and concurrency: when two people act at the same time
part: Part 1 · SQL and Postgres
summary: Lost updates, row locks, isolation levels, deadlocks, and the safe way to reduce stock.
---

**A transaction is a bundle of statements that either all happen or none happen. Concurrency is what goes wrong when many bundles run at the same time, and the database gives you tools to prevent it.**

In this chapter, we will learn:

- What a transaction guarantees
- The **lost update**, the most common concurrency bug in backends
- Three ways to fix it: atomic `UPDATE`, a guard, and `SELECT ... FOR UPDATE`
- What isolation levels are, and what Postgres does by default
- Deadlocks, and how to avoid them
- Why the cure for many of these is "retry"

Let's get started.

## The last chai

ChaiPoint has 200 Masala chai in stock. Asha and Ravi both tap "Order 2 chai" at the same moment. Two requests reach the API, and each one runs on its own database connection. The stock should go from 200 to 196.

On your phone, this never happens: Room has one app, one process. On a server, many requests run **at the same time**, and your code is no longer the only one touching the data.

!!! android "Android parallel"
    You may remember that SQLite lets one writer in at a time, so two coroutines in your app queue up. Postgres is built for many writers at once. That is a strength, and it means **you** must think about what happens when two of them touch the same row.

## What a transaction gives you

From the PostgreSQL tutorial: a transaction "bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all." And once a transaction is acknowledged, it "has indeed been permanently recorded and won't be lost even if a crash ensues shortly thereafter".

```text
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE name = 'Alice';
UPDATE accounts SET balance = balance + 100 WHERE name = 'Bob';
COMMIT;              -- both happen, or (on ROLLBACK / crash) neither
```

The tutorial also says that "PostgreSQL actually treats every SQL statement as being executed within a transaction": a statement alone is a tiny transaction of its own.

!!! android "Android parallel"
    `roomDatabase.withWriteTransaction { dao.insert(a); dao.update(b) }` is the same idea. The Room guide shows exactly this helper to run several DAO operations as one transaction.

But a transaction does **not**, by itself, stop two requests from overwriting each other. Let's see that.

## The lost update

Here is the code that most of us write first. Read the stock, subtract in code, write it back:

```python
stock = db.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]
db.execute("UPDATE products SET stock = %s WHERE id = 1", (stock - 2,))
```

It looks correct. Press Play and watch what two requests do to it.

```seq
{"actors":[{"name":"Order A","kind":"app"},{"name":"Order B","kind":"app"},{"name":"Postgres","kind":"db"}],
 "intro":"Two requests, one row. Stock starts at 200.",
 "messages":[
  {"from":0,"to":2,"text":"SELECT stock","caption":"Order A reads the stock."},
  {"from":2,"to":0,"text":"200","dashed":true,"caption":"Postgres answers 200."},
  {"from":1,"to":2,"text":"SELECT stock","caption":"Before A writes anything, Order B reads the stock too."},
  {"from":2,"to":1,"text":"200","dashed":true,"caption":"B also sees 200. It is true at this moment."},
  {"from":1,"to":2,"text":"SET stock = 198","caption":"B calculates 200 - 2 and writes 198."},
  {"from":0,"to":2,"text":"SET stock = 198","caption":"A is slower. It also calculated 200 - 2, so it writes 198 and overwrites B's work."},
  {"from":2,"text":"stock = 198","kind":"bad","caption":"Two orders of 2 chai were accepted, but stock went down by only 2. One order is lost. The customer is happy, the kitchen is short."}]}
```

I did not make up this picture. I ran it with two real connections, forcing A to be slow. The script is `demos/ch08_concurrency.py` in this course's repository:

```text
A read stock = 200
B read stock = 200
B wrote 198
A wrote 198
final stock = 198   (two orders of 2 should leave 196)
```

No error, no warning, wrong data. This is a **lost update**. It happens because "read, think in Python, write" is three separate steps, and another request can slip in between them.

## Fix 1: let the database do the arithmetic

The simplest fix is to not read at all:

```sql
UPDATE products SET stock = stock - 2 WHERE id = 1;
```

This is one statement. If two arrive together, the second one waits for the first to finish, then works on the new value. On my machine, running it from two connections at once left `stock = 196`, as it should.

## Fix 2: add a guard, and look at the row count

Subtracting is not enough if stock must never go below zero. Add the condition to the statement itself:

```sql
UPDATE products SET stock = stock - 2 WHERE id = 1 AND stock >= 2;
```

Then, in Python, read how many rows changed (`cursor.rowcount`). `1` means "order accepted", `0` means "not enough stock". Remember from chapter 4 that zero rows is not an error, so you must check.

Is this safe when two orders arrive at the same time? Here the manual's description of the default isolation level answers it: when a second updater has to wait for the first, then once the first commits, the second "will attempt to apply its operation to the updated version of the row. The search condition of the command (the WHERE clause) is re-evaluated to see if the updated version of the row still matches the search condition."

I tested it with only 3 in stock and two orders of 2 at the same instant, three times. Every time, exactly one order got `1`, the other got `0`, and the final stock was `1`. Which one won changed from run to run, and that is fine. It never went negative.

```text
rows updated: A = 0, B = 1  (1 = order accepted, 0 = refused)
final stock = 1
```

!!! tip "The best fix is often the simplest"
    A single `UPDATE ... SET x = x - n WHERE ... AND x >= n`, plus a check of the row count, handles a large share of "two people, one counter" problems. Reach for locks only when you need more.

## Fix 3: lock the row with SELECT ... FOR UPDATE

Sometimes you must read first, decide in Python, and then write. For that, tell Postgres "I am going to change this row, nobody else touch it until I finish":

```sql
BEGIN;
SELECT stock FROM products WHERE id = 1 FOR UPDATE;
-- decide in Python...
UPDATE products SET stock = 198 WHERE id = 1;
COMMIT;
```

The manual says `FOR UPDATE` "prevents them from being locked, modified or deleted by other transactions until the current transaction ends", and that other transactions trying the same "will be blocked until the current transaction ends". It also says the lock is held until the end of the transaction. And importantly: "Row-level locks do not affect data querying; they block only writers and lockers to the same row."

Here is my real run. Session A locks the row. Session B asks for the same row and **waits**. A commits after 1.5 seconds, and only then does B get its answer:

```text
[ 0.0s] A locked the row, stock = 200
[ 0.0s] B asks for the same row ...
[ 1.5s] A committed 198
[ 1.5s] B got the row, stock = 198
[ 1.5s] B committed 196
final stock = 196
```

B did not read the stale `200`. It waited, and then saw `198`. That is the whole point of the lock.

!!! warning "Keep locked transactions short"
    While A holds the lock, B just waits. Do not call another web service, send an email, or wait for the user while you hold a lock. Lock, change, commit, and do the slow things afterwards.

```flow
{"width":720,"height":190,"intro":"A row lock makes the second session wait its turn.",
 "nodes":[
  {"id":"a","label":"Session A","sub":"FOR UPDATE","x":10,"y":70,"kind":"app","w":140},
  {"id":"r","label":"Row: stock","sub":"locked by A","x":290,"y":70,"kind":"db","w":150},
  {"id":"b","label":"Session B","sub":"FOR UPDATE","x":570,"y":70,"kind":"app","w":140}],
 "edges":[{"from":"a","to":"r","label":"lock"},{"from":"b","to":"r","label":"waits"}],
 "steps":[
  {"edges":[0],"nodes":["a","r"],"labels":["lock"],"text":"A takes the lock on the row."},
  {"edges":[1],"nodes":["b"],"labels":["wait"],"text":"B asks for the same row. It is not refused, it is put in a queue."},
  {"nodes":["r"],"text":"A commits and the lock is released. Now B gets the row, with A's change already in it."}]}
```

## Readers do not wait: MVCC

You may ask: if writers lock rows, do readers get stuck? No. Postgres keeps several versions of a row (this is called MVCC, multiversion concurrency control). The manual says: "reading never blocks writing and writing never blocks reading." Each statement sees a consistent snapshot, so a long report does not stop orders from coming in.

## Isolation levels: what can I see while others change data?

Each transaction runs at an **isolation level**, which decides what it sees of other people's changes. Postgres has three that really differ, and the default is the first.

| Level | What you see | If there is a conflict |
|---|---|---|
| **Read Committed** (default) | Each statement sees data committed before **that statement** started | The second updater waits, then re-checks its `WHERE` (as above) |
| **Repeatable Read** | The whole transaction sees one snapshot, from its first statement | A conflicting update fails with a **serialization error**: you retry |
| **Serializable** | As if transactions ran one after another | May fail with a serialization error: you retry |

I ran the same steps at the first two levels. B reads the stock, then A commits a change to `150`, then B reads again and tries to update:

```text
== Isolation level: READ COMMITTED ==
B first read   : 200
A committed stock = 150 in between
B second read  : 150
B update worked

== Isolation level: REPEATABLE READ ==
B first read   : 200
A committed stock = 150 in between
B second read  : 200
B update failed: SerializationFailure: could not serialize access due to concurrent update
```

In **Read Committed**, B's second read changed to `150`, because A had committed. In **Repeatable Read**, B kept seeing `200`, and when B tried to modify a row that A had changed, Postgres refused with `could not serialize access due to concurrent update`.

That error is not a bug. The manual's instruction is exact: "it should abort the current transaction and retry the whole transaction from the beginning. The second time through, the transaction will see the previously-committed change as part of its initial view of the database."

**Serializable** is the strictest. The manual says it "emulates serial transaction execution for all committed transactions" and "applications using this level must be prepared to retry transactions due to serialization failures". It can fail with `could not serialize access due to read/write dependencies among transactions`, and you retry that as well.

You choose the level per transaction, for example with `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` right after `BEGIN`. For most CRUD code, the default plus the three fixes above is enough. Use the stricter levels when a decision depends on **several** rows that others may change, and be ready to retry.

## Deadlocks

If transaction A holds row 1 and wants row 2, while B holds row 2 and wants row 1, neither can ever continue. The manual's description: "PostgreSQL automatically detects deadlock situations and resolves them by aborting one of the transactions involved, allowing the other(s) to complete." It adds that which one gets aborted "is difficult to predict and should not be relied upon."

My real run, with two sessions locking products 1 and 2 in opposite order:

```text
A: aborted: deadlock detected
B: committed
```

The cure, from the manual: "The best defense against deadlocks is generally to avoid them by being certain that all applications using a database acquire locks on multiple objects in a consistent order." If every order always updates products in ascending `id`, A and B would line up instead of crossing. And when you cannot guarantee it, "deadlocks can be handled on-the-fly by retrying transactions that abort due to deadlocks."

## The common thread: retry, with a limit

Serialization failures and deadlocks are normal events in a busy system, and both have the same answer: run the whole transaction again from the start. In this project, **every retry has a cap** (for example 3 tries) and a short wait. A retry loop without a cap is just a different way to hang. We will build one properly in the Python chapter.

## Summary

- A transaction (`BEGIN ... COMMIT`) is all-or-nothing, and its half-done state is invisible to others.
- "Read in Python, compute, write back" causes **lost updates**. I reproduced it: two orders of 2 left stock at 198 instead of 196.
- Fix with `SET stock = stock - n`, add `AND stock >= n` as a guard and check `rowcount`, or lock with `SELECT ... FOR UPDATE`.
- Readers never block writers (MVCC). Row locks block only other writers of the same row.
- Read Committed is the default. Repeatable Read and Serializable can fail with a serialization error, and your code must retry.
- Deadlocks: lock in a consistent order, and retry if one is detected.

!!! faq "Should I just use Serializable everywhere?"
    It is the safest, and the manual notes that it has "some overhead" for the monitoring, plus you must write retry code. Many teams use the default level with careful single-statement updates and locks, and keep Serializable for the few places that need it.

!!! faq "Do I need a transaction for a single SELECT?"
    No. A single statement is already its own small transaction, and its snapshot is consistent. Use an explicit one when you run several statements that must see the same data, or change several things together.

## Sources

- [PostgreSQL 16 tutorial: Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)
- [PostgreSQL 16 manual: MVCC, Introduction](https://www.postgresql.org/docs/16/mvcc-intro.html)
- [PostgreSQL 16 manual: Transaction Isolation](https://www.postgresql.org/docs/16/transaction-iso.html)
- [PostgreSQL 16 manual: Explicit Locking (row locks, deadlocks)](https://www.postgresql.org/docs/16/explicit-locking.html)
- [Android Developers: Access data using Room DAOs (transaction helpers)](https://developer.android.com/training/data-storage/room/accessing-data)
- The runnable experiments in this chapter: `demos/ch08_concurrency.py` in the course repository.

That's it for now. This ends Part 1. In the next chapter, we will connect a FastAPI service to Postgres, with a connection pool and safe parameters.
