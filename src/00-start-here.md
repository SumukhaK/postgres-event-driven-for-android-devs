---
title: Start here: what you will build and how to use this course
part: Welcome
summary: The plan, the running example, and a Postgres on your laptop in five minutes.
---

**This course teaches SQL, PostgreSQL, and event-driven backends to an Android developer, using the things you already know as the starting point.**

In this course, we will learn:

- How a server database is different from the Room database in your app
- How to read and write SQL without fear
- How Postgres keeps your data correct when many people use it at the same time
- How to talk to Postgres from a FastAPI service
- How to build an event-driven backend with only Postgres, step by step

Let's get started.

## Who is this course for?

You have built Android apps for years. You know Kotlin, ViewModel, Room, coroutines, and WorkManager. You have also learned a little Python and FastAPI.

But the backend is still a bit of a black box. You call an API from the app, and "something" stores the data. This course opens that box.

We assume **no SQL knowledge**. We do assume you are comfortable with `@Entity`, `@Dao`, and `@Query`. Whenever a new idea shows up, we first connect it to something you already know. Look for the green boxes:

!!! android "Android parallel"
    A green box means: "You already know this idea from Android. Here is the same idea on the server."

## The running example: ChaiPoint

Every chapter uses the same small app. **ChaiPoint** is a food-ordering app. You have built one a hundred times on the client side. This time, we build the backend.

```flow
{"width":720,"height":210,"intro":"The whole course is about the right half of this picture.",
 "nodes":[
  {"id":"app","label":"Android app","sub":"ChaiPoint","x":10,"y":80,"kind":"phone"},
  {"id":"api","label":"FastAPI","sub":"the web service","x":200,"y":80,"kind":"app"},
  {"id":"db","label":"PostgreSQL","sub":"orders, products","x":410,"y":20,"kind":"db"},
  {"id":"w","label":"Workers","sub":"email, stock, ...","x":410,"y":140,"kind":"queue"},
  {"id":"mail","label":"Notifications","x":585,"y":140,"w":120}],
 "edges":[{"from":"app","to":"api","label":"POST /orders"},{"from":"api","to":"db","label":"save"},{"from":"db","to":"w","label":"events"},{"from":"w","to":"mail"}],
 "steps":[
  {"edges":[0],"labels":["order"],"nodes":["app"],"text":"The app sends a new order to the API."},
  {"edges":[1],"labels":["INSERT"],"nodes":["api"],"text":"The API saves the order in Postgres. This is the SQL part (Part 1 and 2)."},
  {"edges":[2],"labels":["event"],"nodes":["db"],"text":"Postgres also holds a list of events: 'an order was placed'. Workers read them."},
  {"edges":[3],"labels":["push"],"nodes":["w"],"text":"Workers do the slow jobs in the background: send a message, reduce stock. This is the event-driven part (Part 3)."}]}
```

## The roadmap

| Part | Chapters | What you can do after it |
|---|---|---|
| 1. SQL and Postgres | 1 to 8 | Design tables, write queries, make them fast, keep data correct |
| 2. Python and Postgres | 9 | Connect FastAPI to Postgres safely |
| 3. Event-driven backend | 10 to 14 | Build queues, workers, and the outbox pattern on Postgres |

Read the chapters in order. Each one is short and ends with a summary and a few questions.

## Set up Postgres in five minutes

The easiest way is Docker. Run this once:

```bash
docker run --name chaipoint-db -e POSTGRES_PASSWORD=chai -e POSTGRES_DB=chaipoint -p 5432:5432 -d postgres:16
```

Now connect to it with `psql`, the command-line client:

```bash
docker exec -it chaipoint-db psql -U postgres -d chaipoint
```

You should see a prompt like `chaipoint=#`. Type `SELECT 1;` and press Enter.

```sql
SELECT 1;
```

If you see a table with the number `1`, you are ready.

!!! tip "No Docker?"
    Install Postgres from postgresql.org (or `brew install postgresql@16` on a Mac) and run `createdb chaipoint`. Everything in this course works on any Postgres 14 or newer. We tested it on Postgres 16.

## How to use the diagrams

Many diagrams in this course are animated. Press **Play** to watch the steps, or **Next step** to go one step at a time. The text under the diagram explains what just happened.

## How to practise

Type every example yourself instead of pasting it. Change one thing, run it again, and see what happens. That is how SQL goes from "I read it" to "I know it".

!!! faq "Do I need to know Python well?"
    No. Python only appears in Part 2 and 3, and the code is short. If you can read Kotlin, you can read it.

That's it for now. In the next chapter, we will see where a server database fits and how it differs from Room.
