# Week 7 — Databases: How Applications Organize, Connect, and Retrieve Information

## The central idea

A database is not simply a place where information is saved.

A database system solves several problems at the same time:

- How information is structured
- How pieces of information are connected
- How information is found quickly
- How many users can read and change it at once
- How incorrect data is prevented
- How changes remain reliable if something fails
- How the system continues working as the amount of data grows

The deeper lesson is:

> **Choosing how to store data is an architectural decision.**

Different products have different kinds of information and different ways of accessing it.

There is no single type of database that is best for everything.

---

# 0–5 min — Could Instagram run on an Excel spreadsheet?

Start with a challenge rather than an explanation.

Imagine Instagram stored everything in one enormous Excel file.

```text
Users.xlsx
Posts.xlsx
Comments.xlsx
Likes.xlsx
Followers.xlsx
```

At first, this might actually work.

100 students.

500 posts.

2,000 comments.

You could probably build something around it.

Now increase the scale.

```text
100,000 users
10 million posts
500 million likes
```

At the same time:

- thousands of people are opening the app;
- hundreds are posting;
- thousands are liking posts;
- people are following and unfollowing each other;
- the system is constantly asking for feeds;
- profiles are being updated.

Now ask:

> What exactly starts breaking?

The answer is not simply:

> “Excel cannot hold enough rows.”

Modern storage systems can hold huge amounts of information.

The real problems are deeper.

You need to:

```text
Find one user's posts quickly.

Find the newest 20 posts.

Find everyone a user follows.

Add a new like without interfering with other users.

Prevent the same account from being created twice.

Update millions of records safely.

Allow many computers to access the data simultaneously.
```

That is what database systems are built to handle.

---

# 5–12 min — Spreadsheet versus database

Students already understand spreadsheets, so use them as a baseline.

But make the distinction precise.

## Spreadsheet

A spreadsheet is primarily designed for:

- humans viewing data;
- humans editing data;
- calculations;
- analysis;
- relatively small datasets;
- flexible structure.

Example:

| Name | Grade | School  | Score |
| ---- | ----: | ------- | ----: |
| Maya |    12 | Central |    91 |
| Leo  |    11 | North   |    86 |

A human can look at this immediately.

It is excellent for many problems.

But applications need additional capabilities.

---

## Database

A database is designed primarily for software to:

- store information continuously;
- retrieve specific information quickly;
- update small pieces of information;
- connect related information;
- enforce rules;
- support many simultaneous users;
- recover from failures;
- handle increasingly large datasets.

The important distinction is:

> **A spreadsheet is mostly organized around documents people work with.**

> **A database is organized around data that systems continuously operate on.**

---

## Compare them directly

| Question                      | Spreadsheet                     | Database                                     |
| ----------------------------- | ------------------------------- | -------------------------------------------- |
| Human editing                 | Excellent                       | Possible, but usually through an application |
| Programmatic access           | Possible                        | Core purpose                                 |
| Millions of records           | Often difficult                 | Expected                                     |
| Relationships                 | Mostly manual                   | Built into many database models              |
| Multiple simultaneous updates | Limited compared with databases | Designed for it                              |
| Data rules                    | Often informal                  | Can be enforced                              |
| Fast searching                | Limited                         | Indexes and query engines                    |
| Transactions                  | Weak/nonexistent                | Core feature in relational systems           |
| Permissions                   | Usually document-level          | Can be much more granular                    |
| Application backend           | Sometimes for prototypes        | Standard approach                            |

Important nuance:

Do not tell students:

> "Never use Google Sheets."

Sometimes a spreadsheet is completely reasonable.

Example:

```text
50 organizations
updated once per month
managed by one employee
```

Using a database may be unnecessary.

But:

```text
50,000 users
changing information every second
```

is a fundamentally different problem.

Architecture depends on the problem.

---

# 12–18 min — A database is actually several systems working together

Instead of defining a database as "stored tables," explain what a database engine actually does.

A modern database generally gives you several capabilities.

## 1. Storage

Information must physically exist somewhere.

Disk.

SSD.

Cloud storage.

Memory.

The database manages how that information is physically stored.

---

## 2. Organization

The database knows how data is structured.

For example:

```text
Users

user_id
username
email
created_at
```

---

## 3. Retrieval

You can ask:

```text
Find user 7284.
```

Or:

```text
Find the newest 20 posts from users that Maya follows.
```

The database figures out how to retrieve that information.

---

## 4. Integrity

The database can enforce rules.

```text
email must be unique

user_id cannot be empty

post must belong to an existing user
```

---

## 5. Concurrency

Thousands of people may change information simultaneously.

The database has to prevent those changes from corrupting each other.

---

## 6. Reliability

Imagine money moving between two accounts.

```text
Account A: -$100
Account B: +$100
```

What happens if the system crashes after subtracting $100 but before adding it?

A serious database needs mechanisms to prevent the system from ending in an impossible state.

This introduces the idea of a **transaction**.

---

# 18–28 min — Relational databases: the default choice for many applications

Now introduce SQL databases properly.

Examples:

```text
PostgreSQL
MySQL
SQL Server
SQLite
```

Do not focus on SQL syntax.

Focus on the relational model.

A relational database organizes information into tables and connects those tables using identifiers.

Example: a Discord-like product.

```text
USERS

user_id
username
email
```

```text
SERVERS

server_id
server_name
owner_id
```

```text
CHANNELS

channel_id
server_id
channel_name
```

```text
MESSAGES

message_id
channel_id
user_id
content
created_at
```

The important part is not the tables.

It is the relationships.

```text
USER
  │
  ├── writes ──────> MESSAGE
  │
  └── owns ────────> SERVER
                       │
                       └── contains ───> CHANNEL
                                           │
                                           └── contains ───> MESSAGE
```

Now students should see why IDs matter.

The message does not store:

```text
username = "Alex"
```

as its identity.

It stores:

```text
user_id = 83912
```

Because usernames can change.

The relationship remains stable.

---

# Primary keys and foreign keys

Introduce these terms.

### Primary key

Uniquely identifies one record.

```text
user_id = 83912
```

### Foreign key

Points to another record.

```text
message.user_id = 83912
```

This tells the system:

> This message belongs to this user.

Foreign keys can also prevent invalid relationships.

For example:

```text
user_id = 999999999
```

cannot be attached to a message if that user does not exist.

This is an example of the database protecting the integrity of the product.

---

# 28–34 min — The biggest reason relational databases matter: relationships

Show three relationship patterns.

## One-to-one

```text
User ───── UserSettings
```

One user has one settings record.

---

## One-to-many

```text
YouTube Channel
      │
      ├── Video
      ├── Video
      ├── Video
      └── Video
```

One channel can have many videos.

Each video belongs to one channel.

---

## Many-to-many

This is where relational thinking becomes important.

Example:

```text
PLAYERS ↔ GAMES
```

One player can join many games.

One game can contain many players.

You cannot represent this cleanly with just:

```text
Players
Games
```

You create another table.

```text
GAME_PARTICIPANTS

game_id
player_id
joined_at
team
score
```

Now emphasize an important architectural principle:

> **Sometimes the relationship between two things is itself a thing.**

The relationship has its own information.

```text
When did they join?

What team were they on?

What was their score?

Did they leave early?
```

This is one of the ideas students need to understand before asking an agent to design their schema.

---

# 34–39 min — Why not put everything in one giant table?

Show a deliberately bad database.

```text
username
user_email
video_title
video_description
channel_name
channel_owner
comment
comment_author
comment_date
```

Every comment repeats:

```text
video title
video description
channel name
```

If a video has 50,000 comments, the same video information may be duplicated 50,000 times.

Now the video title changes.

Which copy is correct?

This introduces **normalization**.

Do not teach normal forms.

Teach the idea:

> Store an important fact in one logical place whenever possible.

Instead:

```text
VIDEOS
video_id
title
channel_id
```

```text
COMMENTS
comment_id
video_id
user_id
content
```

The comment points to the video.

It does not copy the entire video.

Explain the tradeoff:

Highly normalized databases reduce duplication and inconsistency.

But sometimes systems deliberately duplicate certain information to make reading faster.

That is called **denormalization**.

This gives students an important architectural insight:

> Database design is often a tradeoff between keeping information clean and retrieving it quickly.

---

# 39–46 min — Queries and why some databases become slow

Now move into query efficiency.

Suppose TikTok has:

```text
10 billion video records
```

You ask:

```text
Find video_id = 82739102731
```

One possible strategy:

Start at row 1.

Check.

Row 2.

Check.

Row 3.

Check.

Continue until you find it.

This is called roughly a **full scan**.

At small scale, this may not matter.

At huge scale, it matters enormously.

---

# Indexes

Introduce an index.

A database index is an additional structure that helps the database locate information without scanning everything.

Think of the back of a textbook.

You do not read every page to find:

```text
Photosynthesis
```

You look at the index.

A database does something conceptually similar.

Without index:

```text
Search millions of records.
```

With appropriate index:

```text
Navigate directly toward matching records.
```

You can lightly introduce the idea that common relational database indexes often use structures such as B-trees.

They do not need to understand how B-trees are implemented.

They need to understand:

> An index makes certain queries faster by creating another organized structure.

But indexes have a cost.

Every time you write data, the index may also need to be updated.

Therefore:

```text
More indexes
≠
automatically better
```

Indexes improve reads but add storage and write overhead.

---

# Query patterns determine database design

This is one of the most important ideas for agentic development.

Students should learn to ask:

> What questions will my application ask the database most often?

Example: messaging application.

Common queries:

```text
Get the newest 50 messages in channel 928.

Get all servers user 739 belongs to.

Find user by email.

Find unread notifications for user 739.
```

Those queries should influence:

- tables;
- relationships;
- indexes;
- database choice.

Tell students:

> Do not design your database only by asking, "What information do I have?"

Also ask:

> "How will my application need to retrieve it?"

That is a much more mature architectural question.

---

# 46–52 min — SQL versus NoSQL

Now introduce the fact that not every database is relational.

The word **NoSQL** covers several different database models.

This distinction should be conceptual.

---

# SQL / relational databases

Examples:

```text
PostgreSQL
MySQL
SQL Server
```

Good when:

- data has clear structure;
- relationships matter;
- consistency matters;
- transactions matter;
- you need flexible queries across connected data.

Examples:

```text
Banking
E-commerce orders
School systems
Project management
Inventory
User accounts
```

For most student applications:

> **A relational database such as PostgreSQL is usually a very good default.**

They should not use five database technologies simply because an agent suggested them.

---

# Document databases

Example:

```text
MongoDB
```

Information is often stored as document-like structures.

Example:

```json
{
  "user_id": 827,
  "username": "Maya",
  "preferences": {
    "theme": "dark",
    "notifications": {
      "email": true,
      "push": false
    }
  }
}
```

This can be useful when records naturally contain nested information and the structure may vary.

But relationships across many document types can become more complicated than in relational databases.

---

# Key-value databases

Example:

```text
Redis
```

Think:

```text
KEY
user:827:session

VALUE
authentication information
```

Extremely useful for fast lookups.

Often used for:

- caching;
- sessions;
- temporary state;
- counters.

Usually not the primary database for an entire complex application.

---

# Graph databases

Example:

```text
Neo4j
```

Designed around nodes and relationships.

Example:

```text
Person
  ↓ follows
Person
  ↓ works_at
Company
  ↓ located_in
City
```

Useful when exploring relationships is the central problem.

Examples:

- social networks;
- fraud networks;
- knowledge graphs;
- supply-chain relationships.

A relational database can also represent these relationships.

The difference is what type of querying the system is optimized for.

---

# Vector databases and vector search

Because students are building AI-enabled products, introduce this clearly.

A vector search system stores or indexes numerical representations called embeddings.

It helps answer:

> Which pieces of information are semantically similar to this question?

Example:

A student asks:

```text
"How do I change my enrollment?"
```

The system might retrieve a document containing:

```text
"Procedure for modifying student registration."
```

Even though the words are different.

Vector search is useful for:

- semantic search;
- retrieval-augmented generation;
- finding similar documents;
- recommendations.

But emphasize:

> **A vector database should usually not be your application's main source of truth.**

You probably should not ask:

```text
What is Maya's current application status?
```

using semantic vector search.

That belongs in a structured database.

You might use:

```text
PostgreSQL
```

for:

```text
application_status = approved
```

and vector search for:

```text
Find documents explaining what happens after approval.
```

This distinction will matter enormously when they start using AI agents.

---

# 52–56 min — Databases at scale

Now introduce what changes when a product grows.

Imagine a database with:

```text
1,000 records
```

Almost any reasonable approach may work.

Now:

```text
100 million records
10,000 requests per second
```

Architecture starts to matter.

Introduce the following concepts lightly.

---

## Vertical scaling

Give one database server:

```text
more CPU
more RAM
faster disk
```

Simple, but eventually limited.

---

## Horizontal scaling

Use multiple machines.

This is more complicated because data may need to be distributed or synchronized.

---

## Replication

Keep copies of data on multiple servers.

Possible reasons:

- reliability;
- faster reads;
- geographic distribution.

---

## Partitioning / sharding

Split a huge dataset into pieces.

For example:

```text
Users 1–10 million → Server A

Users 10–20 million → Server B
```

Real systems use more sophisticated strategies, but the concept matters.

---

## Caching

Sometimes the fastest database query is:

> Don't query the database again.

If millions of people request the same information repeatedly, the system may temporarily store the result somewhere faster.

Example:

```text
Database
↓
Cache
↓
Application
```

The challenge:

What happens when the original data changes?

Now the cached version may become stale.

This introduces another major architectural tradeoff:

> Performance often requires additional copies of information, but additional copies create synchronization problems.

---

# 56–60 min — Database architecture for agentic coding

End with what students actually need when working with coding agents.

An agent may happily generate:

```text
PostgreSQL
MongoDB
Redis
Pinecone
Elasticsearch
```

for a small school project.

That does not mean the architecture is good.

Students need to know how to challenge the agent.

Before generating the database, they should explain:

---

## 1. What entities exist?

```text
Users
Projects
Messages
Documents
```

---

## 2. How are they related?

```text
User
  ↓ creates
Project

Project
  ↓ contains
Document
```

---

## 3. What are the important access patterns?

```text
Find project by ID.

Show user's projects.

Get newest messages in project.

Search documents by meaning.
```

---

## 4. Which information must be exact?

```text
User ID
Project status
Permissions
Payment status
```

These should usually live in a structured source of truth.

---

## 5. Which information needs semantic search?

```text
Documents
Descriptions
Knowledge
Notes
```

This may need vector search.

---

## 6. Which information is temporary?

```text
Login session
Cached results
Temporary calculations
```

This may belong in memory or a cache.

---

## 7. What are the expected data volumes?

```text
100 users?

10,000 users?

10 million users?
```

Do not architect Google-scale infrastructure for 50 users.

But understand what would eventually stop scaling.

---

## 8. Which queries need to be fast?

This helps determine indexes.

Example:

```text
Users log in by email.
```

The email field probably needs an index.

```text
Every page loads projects belonging to user_id.
```

That relationship probably needs an index.

---

## 9. What rules must the database enforce?

```text
Email unique.

Project must have an owner.

Message must belong to an existing project.

Status must come from allowed values.
```

---

## 10. Does an operation need a transaction?

Example:

```text
Reserve the last ticket.

Charge user.

Create booking.
```

If one step fails, what happens?

The student should be able to tell the agent:

> These operations should succeed together or fail together.

---

# One advanced example: ticket sales

Use a simple scenario to tie everything together.

There is one ticket remaining.

Two people click:

```text
BUY
```

at almost exactly the same time.

User A checks:

```text
tickets_remaining = 1
```

User B checks:

```text
tickets_remaining = 1
```

Both attempt to purchase.

A badly designed system may sell the same final ticket twice.

This is a database concurrency problem.

The database needs a safe way to perform something conceptually like:

```text
Check availability
Reserve ticket
Create purchase
Reduce inventory
```

as one controlled operation.

Now students can understand why databases are not equivalent to:

```text
Save some values in a file.
```

They coordinate systems that multiple people are using simultaneously.

---

# The mental architecture students should leave with

By the end of Week 7, they should see data infrastructure roughly like this:

```text
                    APPLICATION
                         │
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼

       RELATIONAL DATABASE        OBJECT STORAGE
       PostgreSQL                 S3 / Blob Storage

       Users                      Images
       Projects                   Videos
       Orders                     PDFs
       Permissions                Large files

              │
              ├───────────────┐
              │               │
              ▼               ▼

           CACHE          VECTOR SEARCH
           Redis          pgvector / vector DB

           Sessions       Semantic retrieval
           Fast reads     Similar documents
```

Not every application needs every box.

A simple product may need only:

```text
PostgreSQL
+
file storage
```

And that may be completely sufficient.

The goal is not to teach students to use more technology.

The goal is to teach them:

> **Use the simplest data architecture that correctly matches the type of information, relationships, queries, reliability requirements, and expected scale of the product.**

---

# What they should now be able to ask a coding agent

Instead of:

> Create a database for this app.

They should be capable of saying something closer to:

> Use PostgreSQL as the primary database because the application's core data is relational. Users can create multiple projects, and projects can have multiple members, so model project membership using a separate join table. Project IDs and user IDs should be stable primary keys. Enforce foreign keys and unique email addresses.
>
> The application frequently queries projects by user ID and messages by project ID and creation time, so design appropriate indexes for those access patterns.
>
> Store uploaded images and PDFs in object storage rather than directly in normal database fields, and store their URLs and metadata in PostgreSQL.
>
> We will later need semantic search across project documents, so use vector embeddings for document retrieval, but PostgreSQL remains the source of truth for users, projects, permissions, and statuses.
>
> Do not introduce Redis or another database unless there is a demonstrated performance need.

That is the level of understanding I would want from them.

They do not need to know how PostgreSQL implements MVCC, how B-tree balancing works, or how distributed consensus algorithms operate.

But they absolutely should understand:

```text
Spreadsheet vs database

Structured vs unstructured data

SQL vs NoSQL

Relational modeling

Primary and foreign keys

One-to-many and many-to-many relationships

Normalization and duplication

Queries and access patterns

Indexes

Transactions

Concurrency

Database constraints

Object storage

Vector search

Caching

Scaling

Source of truth
```

Because those concepts allow them to have an intelligent conversation with an agent about architecture instead of blindly accepting whatever stack the agent generates.
