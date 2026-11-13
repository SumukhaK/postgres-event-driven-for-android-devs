---
title: From Room to Postgres: where does the data really live?
part: Part 1 · SQL and Postgres
summary: Client database versus server database, and what Postgres actually is.
---

**A server database is a program that keeps data safe and lets many apps read and write it at the same time, over the network.**

In this chapter, we will learn:

- Why your app needs a server database even though it has Room
- What PostgreSQL is, and what is inside it
- The vocabulary: database, schema, table, row, column
- How a request travels from your phone to a row on a disk

Let's get started.

## Why do we need a server database?

Imagine two friends, Asha and Ravi, order chai from ChaiPoint on their own phones. Each phone has a Room database. Asha's phone knows about Asha's orders. Ravi's phone knows about Ravi's orders.

Now the kitchen needs to see **both** orders. Neither phone can show that. The data must live in **one shared place**, which every phone and every service can reach. That place is the server database.

```flow
{"width":720,"height":250,"intro":"Two phones, one shared truth.",
 "nodes":[
  {"id":"a","label":"Asha's phone","sub":"Room (local copy)","x":10,"y":20,"kind":"phone","w":150},
  {"id":"r","label":"Ravi's phone","sub":"Room (local copy)","x":10,"y":160,"kind":"phone","w":150},
  {"id":"api","label":"API","sub":"FastAPI","x":300,"y":90,"kind":"app"},
  {"id":"db","label":"PostgreSQL","sub":"the one source of truth","x":520,"y":90,"kind":"db","w":170}],
 "edges":[{"from":"a","to":"api","label":"order"},{"from":"r","to":"api","label":"order"},{"from":"api","to":"db","label":"INSERT"}],
 "steps":[
  {"edges":[0],"labels":["chai x2"],"text":"Asha orders two chai. Her phone sends the order to the API."},
  {"edges":[1],"labels":["tea x1"],"text":"Ravi orders at the same moment from another phone."},
  {"edges":[2],"labels":["both"],"nodes":["db"],"text":"The API writes both orders into Postgres. Now the kitchen, the delivery app, and the report page can all read the same data."}]}
```

!!! android "Android parallel"
    In your app, Room is a **cache and a local store**. The server database is the **source of truth**. When the app and the server disagree, the server wins. That is why your sync code (WorkManager, Retrofit) exists.

## Room, SQLite, and Postgres: the same family

Room is a friendly wrapper over **SQLite**. SQLite and PostgreSQL are both **relational databases**: data lives in tables, and you talk to them with **SQL**. So everything you know about `@Entity` and `@Query` carries over.

The differences are about **who uses it**:

| | SQLite (inside Room) | PostgreSQL |
|---|---|---|
| Where it runs | Inside your app process, as a file | A separate server program |
| Who connects | One app | Many apps and services, over the network |
| Many writers at once | One at a time | Many at the same time |
| Users and permissions | None (the file is the app's) | Roles, passwords, per-table permissions |
| Extras | Small and simple | Rich types (JSON, arrays, UUID), full-text search, extensions |

## What is inside Postgres?

Think of Postgres like a building:

- The **server** is the building. It runs all the time.
- A **database** is one office in the building. ChaiPoint gets its own, called `chaipoint`.
- A **schema** is a room in that office. The default room is called `public`.
- A **table** is a filing cabinet in the room. `orders` is one table.
- A **row** is one paper in the cabinet. One order is one row.
- A **column** is a field printed on every paper, such as `status` or `total`.

```flow
{"width":720,"height":200,"intro":"From the big box to the small box.",
 "nodes":[
  {"id":"s","label":"Server","sub":"postgres process","x":10,"y":70,"w":120,"kind":"db"},
  {"id":"d","label":"Database","sub":"chaipoint","x":170,"y":70,"w":120},
  {"id":"sc","label":"Schema","sub":"public","x":330,"y":70,"w":110},
  {"id":"t","label":"Table","sub":"orders","x":480,"y":70,"w":100},
  {"id":"r","label":"Row","sub":"order #7","x":615,"y":70,"w":95}],
 "edges":[{"from":"s","to":"d"},{"from":"d","to":"sc"},{"from":"sc","to":"t"},{"from":"t","to":"r"}],
 "steps":[
  {"nodes":["s"],"text":"One Postgres server runs on a machine and waits for connections."},
  {"nodes":["s","d"],"edges":[0],"text":"Inside it live one or more databases. Each is separate, with its own tables."},
  {"nodes":["d","sc"],"edges":[1],"text":"A database is split into schemas. If you do nothing, you use the one named public."},
  {"nodes":["sc","t"],"edges":[2],"text":"Schemas hold tables."},
  {"nodes":["t","r"],"edges":[3],"text":"And tables hold rows. This is where your data is."}]}
```

## What happens when your app asks for an order?

Postgres does not know about HTTP or Android. It only understands one language, **SQL**, sent over a TCP connection.

```seq
{"actors":[{"name":"Android app","kind":"phone"},{"name":"FastAPI","kind":"app"},{"name":"PostgreSQL","kind":"db"}],
 "intro":"One request, from tap to disk and back.",
 "messages":[
  {"from":0,"to":1,"text":"GET /orders/7","caption":"The app calls the API with Retrofit. It knows nothing about SQL."},
  {"from":1,"to":2,"text":"SELECT ... WHERE id = 7","caption":"The API sends a SQL query over a connection to Postgres."},
  {"from":2,"text":"find row on disk","caption":"Postgres finds the row (using an index if there is one, see chapter 7) and reads it."},
  {"from":2,"to":1,"text":"1 row","dashed":true,"caption":"Postgres sends the row back."},
  {"from":1,"to":0,"text":"JSON","dashed":true,"caption":"The API turns the row into JSON, and the app shows it on screen."}]}
```

Notice the API sits between the app and the database. **The app never talks to Postgres directly.** The API checks who you are, validates the input, and only then runs SQL. That is a security rule you should keep.

## Summary

- A server database is the shared source of truth. Room on the phone is a local copy.
- PostgreSQL is a relational database server. You talk to it in SQL.
- It is organised as server, database, schema, table, row, and column.
- Your Android app calls an API. The API runs SQL.

!!! faq "Can I put Postgres inside my Android app?"
    No. Postgres is a server program. On a phone you use SQLite, usually through Room.

!!! faq "Is SQL the same everywhere?"
    The core (`SELECT`, `INSERT`, `JOIN`) is the same in SQLite, Postgres, and MySQL. Details differ. This course uses Postgres.

That's it for now. In the next chapter, we will create the tables for ChaiPoint.
