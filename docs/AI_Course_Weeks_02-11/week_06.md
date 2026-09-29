# Week 6 — Backend: Where the Product Becomes Real

By Week 6, students should already understand:

- A product is made of different parts.
- Some computation happens on the user’s device and some happens remotely.
- Data can live in files, databases, object storage, or external systems.
- The internet moves requests and responses between computers.
- The frontend is the part of the system the user directly interacts with.

Now Week 6 should connect all of that.

The backend is not simply “the invisible part.”

The backend is the part of the system that **coordinates the product**.

It sits between:

```text
What the user wants
        ↓
What the product allows
        ↓
What data exists
        ↓
What computation must happen
        ↓
What other systems are needed
        ↓
What changes permanently
        ↓
What result goes back to the user
```

This is the central idea of the lecture.

The frontend captures **intent**.

The backend turns that intent into **controlled changes in the system**.

---

# Start with the complete system they already know

Do not begin by introducing another disconnected concept.

Put the architecture from the previous weeks back on the screen:

```text
USER
  ↓
FRONTEND
  ↓
INTERNET
  ↓
BACKEND
  ↓
COMPUTATION
  ↓
DATA / STORAGE
  ↓
OTHER SYSTEMS
  ↓
BACKEND
  ↓
INTERNET
  ↓
FRONTEND
  ↓
USER
```

Then ask:

> We already understand the frontend.
>
> We already understand that data is stored somewhere.
>
> We already understand that computers perform computation.
>
> We already understand how requests travel across the internet.
>
> So what exactly is the backend?

The answer:

> The backend is the part that decides how all of those pieces work together to produce the behavior of the product.

That distinction matters.

A database can store that a Spotify user has liked 842 songs.

A computer can calculate recommendations.

An AI model can classify music.

An external service can process payments.

But something has to decide:

- When each thing should happen
- In what order
- Using which information
- Under which rules
- For which user
- What happens if something fails
- What gets permanently changed

That coordinating logic is the backend.

---

# The backend is the product’s operating system

A useful mental model is:

```text
Frontend = What the user can see and ask for

Backend = The system that decides what actually happens

Database = What the system remembers
```

These three are related, but they are not interchangeable.

For example, imagine Spotify.

The frontend shows:

```text
♥ Like Song
```

The database may contain:

```text
User 9182
likes
Song 55102
```

But the backend controls the process between those two things.

```text
User presses Like
        ↓
Frontend says:
"User wants to like Song 55102"
        ↓
Backend receives the request
        ↓
Backend determines which user made the request
        ↓
Backend checks whether the song exists
        ↓
Backend checks whether the relationship already exists
        ↓
Backend creates the relationship
        ↓
Backend updates whatever other systems depend on that action
        ↓
Backend returns the new state
        ↓
Frontend shows the filled heart
```

The important insight is:

The button does not “like the song.”

The database does not “decide to like the song.”

The backend manages the transition:

```text
NOT LIKED
    ↓
LIKED
```

This introduces one of the most important ideas in software architecture.

# Products are systems that move between states

A backend is largely responsible for controlling those state changes.

---

# Part 1 — Think in state transitions, not buttons

Students building with agents often make this mistake:

```text
I need a button called Approve.
```

That is frontend thinking.

The better question is:

```text
What happens to the system when something becomes approved?
```

Suppose the product contains scholarship applications.

An application may move through:

```text
Draft
  ↓
Submitted
  ↓
Under Review
  ↓
Approved
```

Or:

```text
Under Review
  ↓
Needs More Information
```

Or:

```text
Under Review
  ↓
Rejected
```

Each transition has consequences.

For example:

```text
Under Review → Approved
```

may mean:

- The reviewer must have permission.
- The application cannot already be rejected.
- The approval time must be recorded.
- The reviewer ID must be recorded.
- The applicant may need a notification.
- Funding capacity may need to be checked.
- The application should no longer be editable.

So the backend is not merely:

```text
approve_application()
```

The real question is:

> What is allowed to move from one state to another, who can cause that change, and what else must happen when it changes?

This is how students should start thinking before asking an agent to build anything.

---

# The first major backend design question

## What is the state of the system?

Before coding, students should identify the important things that can change.

Examples:

For a food delivery order:

```text
Cart
Order Created
Payment Confirmed
Restaurant Accepted
Preparing
Ready
Picked Up
Delivered
Cancelled
```

For a multiplayer game:

```text
Offline
Searching for Match
Match Found
Joining
Playing
Finished
Disconnected
```

For an AI research task:

```text
Created
Collecting Data
Processing
Generating
Needs Review
Completed
Failed
```

For the students' project platform:

```text
Idea
Project Draft
Teacher Review
Organization Outreach Ready
Outreach Sent
Organization Responded
Project Active
Completed
```

Then ask:

> Which transitions are legal?

For example:

Can a project go directly from:

```text
Idea → Completed
```

Probably not.

Can an email go from:

```text
Draft → Sent
```

without student confirmation?

Maybe not.

Can a rejected scholarship application suddenly become:

```text
Paid
```

without approval?

Definitely not.

This is backend architecture.

The code comes afterward.

---

# Part 2 — The backend creates a boundary of trust

Now connect this lesson to what they learned about frontend and the internet.

The frontend runs on a device the user controls.

The backend runs on infrastructure controlled by the product.

That creates a critical boundary.

```text
USER'S DEVICE
Frontend
    |
    |  Request crosses the internet
    |
---------------- TRUST BOUNDARY ----------------
    |
Backend
Database
Internal Systems
```

Everything crossing that boundary must be treated as a request.

Not as truth.

This is one of the most important concepts students need when steering coding agents.

Suppose a game frontend sends:

```text
player_id = 917
coins_to_add = 1000000
```

Should the backend simply add one million coins?

Obviously not.

Suppose an e-commerce frontend sends:

```text
product_id = 42
price = $1.00
```

But the real price is $800.

Should the backend trust the frontend?

No.

Suppose a school application sends:

```text
student_id = 9182
role = administrator
```

Should the backend believe the role?

No.

The backend should establish important facts itself.

For example:

```text
Frontend says:
"I want to buy product 42."

Backend determines:
Who the user is
What product 42 costs
Whether it is available
Whether the user can buy it
How much should be charged
```

This leads to a powerful rule:

> The frontend tells the backend what the user wants to do.
>
> The backend determines what is actually true.

When students ask coding agents to build systems, this is one of the first things they should inspect.

Ask the agent:

```text
Which information are you trusting from the frontend?

Which information are you verifying on the backend?

Which system is the source of truth?
```

---

# Part 3 — Source of truth

This concept should connect directly to the previous storage lesson.

Imagine Instagram shows:

```text
12,482 followers
```

Where does that number come from?

Maybe it is calculated from relationships stored in a database.

Maybe it is cached somewhere for speed.

Maybe multiple systems maintain versions of it.

But somewhere there must be an authoritative answer.

That is the **source of truth**.

For example:

```text
Database:
User follows another user
```

may be the source of truth.

The frontend display is not.

A cached count may not be.

An AI answer definitely is not.

This matters enormously when using coding agents because agents will often create duplicate copies of data unless instructed otherwise.

Suppose the system stores:

```text
Student Profile:
county = Tulsa
```

And also stores:

```text
Project:
student_county = Tulsa
```

And also stores:

```text
Recommendation:
student_county = Tulsa
```

What happens when the student moves?

Now three places contain the same information.

Which one is correct?

Students need to understand:

> A backend should know which system owns each important piece of information.

Then other parts of the product should reference or derive from that source whenever practical.

This leads to a backend design question:

```text
Where does this fact live?

Who is allowed to change it?

Who reads it?

Do we store another copy, or calculate it when needed?
```

---

# Part 4 — Follow one request through the backend

Now introduce the actual internal structure.

Not as random capabilities.

As a pipeline.

Take something familiar:

```text
User presses:
"Reserve Seat"
```

The backend request may move through several conceptual stages.

```text
REQUEST
   ↓
IDENTIFY
   ↓
VALIDATE
   ↓
AUTHORIZE
   ↓
APPLY RULES
   ↓
READ CURRENT STATE
   ↓
PERFORM OPERATION
   ↓
CHANGE STATE
   ↓
TRIGGER SIDE EFFECTS
   ↓
RETURN RESULT
```

This is the mental model.

Now explain each step as part of one continuous process.

---

## 1. Request

The backend receives:

```text
Reserve seat 14C on Flight 817
```

The request represents intent.

Nothing has happened yet.

---

## 2. Identify

The backend determines:

```text
Who is asking?
```

Maybe:

```text
User 9182
```

This identity should come from a trusted login session, token, or authentication system.

Not from:

```text
user_id = 9182
```

typed by the browser.

---

## 3. Validate

The backend checks whether the request makes sense.

For example:

```text
Does flight 817 exist?
Does seat 14C exist?
Is the request formatted correctly?
```

---

## 4. Authorize

Now:

```text
Is this user allowed to perform this action?
```

Maybe the user is booking for themselves.

Maybe an airline employee is booking for someone else.

Maybe the account is restricted.

This is different from validation.

A perfectly valid request can still be unauthorized.

---

## 5. Read current state

Now the backend asks:

```text
Is seat 14C currently available?
```

This is where the database becomes involved.

The important word is:

```text
currently
```

The backend must make decisions based on the state of the system now.

---

## 6. Apply product rules

Maybe:

```text
Exit row seats require certain eligibility.
```

Maybe:

```text
This fare does not allow seat selection.
```

Maybe:

```text
The reservation has expired.
```

These rules define how the product operates.

---

## 7. Perform the operation

The backend changes:

```text
Seat 14C
AVAILABLE
```

to:

```text
Seat 14C
RESERVED FOR USER 9182
```

This is the actual system change.

---

## 8. Trigger side effects

Other things may happen because of the reservation.

For example:

```text
Update seat map
Send confirmation
Record analytics
Update loyalty system
```

These are consequences of the main action.

They are not necessarily the main action itself.

That distinction becomes important later.

---

## 9. Return the result

The backend responds:

```text
Reservation confirmed.
Seat: 14C
```

The frontend then displays it.

The frontend did not reserve the seat.

It displayed the result of the backend successfully changing the system.

---

# Part 5 — The most important backend problem: two things happen at once

This is where the class can become more interesting.

Ask:

> What happens if two people try to reserve seat 14C at exactly the same time?

Both users see:

```text
14C — Available
```

Then both press:

```text
Reserve
```

at almost exactly the same moment.

Now the backend receives:

```text
Request A
Reserve 14C
```

and:

```text
Request B
Reserve 14C
```

If the backend is badly designed:

```text
A checks: available
B checks: available

A reserves
B reserves
```

Now two people own the same seat.

The frontend looked perfectly fine.

The database existed.

The internet worked.

The backend code ran.

But the system was still wrong.

This is why backend architecture matters.

Students do not need to master database transactions yet.

But they must understand the concept:

> Some operations must be treated as one protected change.

The system needs something conceptually like:

```text
Check if seat is available
AND
reserve it
as one controlled operation
```

This introduces:

# Atomic operations

An operation is atomic when the important change either:

```text
happens completely
```

or:

```text
does not happen
```

Not halfway.

Use another example.

Transferring $100:

Bad:

```text
Remove $100 from Account A
        ↓
System crashes
        ↓
Never add $100 to Account B
```

The backend cannot treat those as unrelated operations.

Students should learn to ask coding agents:

```text
Could two users perform this action at the same time?

Could this operation partially succeed?

Does this need a transaction or another concurrency control?
```

They do not need to know how to implement every technique.

They need to know that the problem exists.

That is the level at which they can steer agents intelligently.

---

# Part 6 — Separate the main action from the side effects

Now go one level deeper.

Suppose a student submits a project.

The important action is:

```text
Project state:
Draft → Submitted
```

Other things may happen:

```text
Email teacher
Send push notification
Generate AI summary
Update analytics
Post message to Slack
```

Ask:

> If the Slack message fails, should the project submission disappear?

No.

> If the AI summary fails, should the project become unsubmitted?

Probably not.

This creates an important architectural distinction.

```text
CORE OPERATION
```

versus:

```text
SIDE EFFECTS
```

For example:

```text
CORE
Save order

SIDE EFFECTS
Send receipt
Notify warehouse
Update analytics
Recommend similar products
```

Students should design the backend so they know which operation defines success.

For an online purchase:

```text
Payment succeeded
Order created
```

may be essential.

But:

```text
Marketing email sent
```

is not.

For a project platform:

```text
Project saved
```

is essential.

```text
AI generated a nice summary
```

may not be.

This helps students make systems more resilient.

It also gives them a useful instruction for coding agents:

```text
Identify the core transaction separately from optional side effects.
Do not make a non-critical integration failure destroy the core operation.
```

---

# Part 7 — Immediate work versus work that can happen later

Now connect backend design to the user experience.

Suppose the user presses:

```text
Generate My Annual Report
```

The backend needs to:

- Read thousands of records
- Analyze them
- Generate charts
- Call AI
- Create a PDF
- Upload the file

Maybe this takes 45 seconds.

One design is:

```text
Frontend
   ↓
Request
   ↓
Backend works for 45 seconds
   ↓
User stares at spinner
```

Another design is:

```text
Frontend
   ↓
Request
   ↓
Backend creates Job 817
   ↓
Immediately returns:
"Report is being generated"
   ↓
Worker processes Job 817
   ↓
Report becomes ready
   ↓
User is notified
```

This introduces:

```text
Synchronous work
```

The user waits for completion.

versus:

```text
Asynchronous work
```

The backend starts the work and completes it separately.

Now students can reason about architecture.

Ask:

Should these be synchronous?

```text
Check password
Add item to cart
Load profile
```

Probably.

Should these be asynchronous?

```text
Process 2GB video
Generate 100-page report
Analyze 10,000 documents
Send 50,000 emails
```

Probably.

The backend architecture changes depending on the answer.

When working with coding agents, students should ask:

```text
Which operations happen during the request?

Which operations should be delegated to a background worker?

How does the frontend know the job status?
```

---

# Part 8 — Stateless requests and persistent state

This is another critical conceptual distinction.

Most backend requests should be understandable independently.

For example:

```text
GET /profile
```

The backend receives the request and retrieves the current profile.

The backend should not depend on the same physical server remembering:

```text
"Oh yes, this person visited me five minutes ago."
```

Why?

Because the next request may go to another server.

```text
Request 1 → Server A
Request 2 → Server C
Request 3 → Server B
```

When systems scale, requests can move across multiple machines.

Therefore, important state usually needs to live somewhere persistent:

```text
Database
Cache
Session store
Object storage
Queue
```

Not only inside the memory of one backend process.

This is a subtle but valuable idea for students using cloud coding agents.

A prototype may work because:

```text
users = []
```

exists in memory.

Then the server restarts.

Everything disappears.

Or the platform creates two server instances.

Now:

```text
Server A knows one thing
Server B knows another
```

The product becomes inconsistent.

Students should recognize the difference between:

```text
temporary memory used during computation
```

and:

```text
persistent state belonging to the product
```

This connects directly back to Week 3 and the storage lesson.

---

# Part 9 — A backend is usually organized into layers

Now students are ready to understand why backend code is often separated.

A useful simplified architecture:

```text
                REQUEST
                   ↓

        ┌─────────────────────┐
        │    API / ROUTES     │
        │                     │
        │ Receives requests   │
        │ Returns responses   │
        └──────────┬──────────┘
                   ↓

        ┌─────────────────────┐
        │  BUSINESS LOGIC     │
        │                     │
        │ Product rules       │
        │ Workflows           │
        │ Decisions           │
        └──────────┬──────────┘
                   ↓

        ┌─────────────────────┐
        │    DATA ACCESS      │
        │                     │
        │ Read/write database │
        └──────────┬──────────┘
                   ↓

              DATABASE
```

Other branches may exist:

```text
BUSINESS LOGIC
     ├── AI MODEL
     ├── PAYMENT API
     ├── EMAIL SERVICE
     ├── FILE STORAGE
     └── BACKGROUND QUEUE
```

Explain why separating these concerns matters.

Suppose the backend mixes everything into one giant function:

```text
Receive request
Check permissions
Run SQL
Call OpenAI
Send email
Calculate score
Save result
Generate response
```

It may work.

But when something changes, the system becomes difficult to understand.

A better design separates responsibilities.

The route knows:

```text
Which request came in?
```

The business logic knows:

```text
What should happen?
```

The data layer knows:

```text
How do we read and write the data?
```

The integration layer knows:

```text
How do we communicate with another service?
```

Students do not need to become experts in design patterns.

But they should recognize when an agent generates:

```text
one 2,000-line backend file
```

and ask whether the responsibilities should be separated.

---

# Part 10 — The backend is not necessarily one server

This is another misconception worth correcting.

Students may imagine:

```text
Frontend
   ↓
Backend
   ↓
Database
```

as three physical computers.

Sometimes a small application really is close to that.

But “backend” describes a responsibility more than one machine.

A simple product might have:

```text
Frontend
   ↓
One backend application
   ↓
One database
```

A larger product might have:

```text
Frontend
   ↓
API
   ↓
Authentication Service
   ↓
Order Service
   ↓
Recommendation Service
   ↓
Payment Service
   ↓
Notification Service
```

Students should understand the tradeoff.

More services can provide:

- Independent scaling
- Clear responsibility
- Team separation
- Failure isolation

But they also introduce:

- More infrastructure
- More network communication
- More failure points
- More debugging complexity
- Harder data consistency

Therefore:

> More architecture is not automatically better architecture.

This is particularly important when coding with AI agents.

Agents often happily create:

```text
microservices
Redis
Kafka
Kubernetes
three databases
event buses
```

for a product that has nine users.

Students need the confidence to say:

```text
No.

Start with one backend application and one database.

Separate the code logically.

We can split services later if scale or complexity requires it.
```

This is good architecture.

---

# Part 11 — Backend design is a sequence problem

One of the best ways for students to reason about a backend is to ask:

```text
What happens first?

What happens next?

What must succeed before something else can happen?

What can happen independently?
```

Consider purchasing concert tickets.

Bad mental model:

```text
Buy ticket
```

Better mental model:

```text
Identify user
        ↓
Find event
        ↓
Check ticket availability
        ↓
Temporarily hold ticket
        ↓
Process payment
        ↓
If payment succeeds:
    confirm ticket
        ↓
If payment fails:
    release hold
        ↓
Generate ticket
        ↓
Send confirmation
```

Now architecture becomes visible.

The students can ask:

- When does the ticket become unavailable to other people?
- What happens if payment takes 30 seconds?
- What happens if payment succeeds but confirmation email fails?
- What happens if the user refreshes?
- What happens if they press Pay twice?
- What happens if the payment provider sends the same success notification twice?

These questions are more valuable than:

```text
Should I use Python or JavaScript?
```

The language is rarely the hardest decision.

The workflow is.

---

# Part 12 — Idempotency: “What if the same request happens twice?”

Introduce this because it is extremely useful when building real products with agents.

Suppose someone presses:

```text
Pay
```

The request is sent.

The internet is slow.

The user presses again.

Now the backend receives:

```text
PAY REQUEST
PAY REQUEST
```

Should they be charged twice?

No.

The same thing happens when systems retry automatically.

A network failure might mean:

```text
The backend processed the request
```

but:

```text
The frontend never received the response
```

So the frontend tries again.

The backend needs a way to recognize:

```text
This is the same operation.
```

This idea is called:

# Idempotency

Conceptually:

```text
Performing the same request again
should not accidentally create
a second version of something
that should only happen once.
```

Examples where students should think about this:

- Payments
- Creating orders
- Submitting applications
- Sending outreach emails
- Awarding game rewards
- Booking appointments
- Creating AI jobs

This is exactly the kind of issue coding agents may miss unless someone asks.

---

# Part 13 — Where should AI live in the backend?

Now connect this to the AI course.

AI should be viewed as one backend capability.

Not as the backend itself.

A strong architecture might look like:

```text
User request
    ↓
Backend
    ↓
Retrieve trusted data
    ↓
Apply deterministic rules
    ↓
Build AI context
    ↓
Call model
    ↓
Validate AI output
    ↓
Apply product rules again if necessary
    ↓
Store approved result
    ↓
Return result
```

For example, suppose students build an AI system that recommends community projects.

Weak architecture:

```text
Send everything to AI.

Ask:
"What project should this student do?"
```

Better architecture:

```text
Backend reads student profile
        ↓
Backend retrieves available projects
        ↓
Backend removes projects that are:
    inactive
    geographically impossible
    age restricted
    unavailable
        ↓
Backend sends remaining candidates to AI
        ↓
AI reasons about qualitative fit
        ↓
Backend validates returned project IDs
        ↓
Backend saves recommendations
        ↓
Frontend displays them
```

The backend surrounds the AI.

AI exists inside the product’s rules.

Not above them.

This is probably one of the most important architectural concepts in the entire course.

---

# Part 14 — The five questions students should ask before telling an agent to build a backend

At this point, reduce the entire lecture into a powerful design framework.

Before writing backend code, answer these five questions.

---

## Question 1

# What is the state of the system?

What important things exist?

What can change?

For example:

```text
Project
Student
Organization
Application
Message
Recommendation
```

And what states can they have?

```text
Draft
Submitted
Approved
Rejected
```

---

## Question 2

# What actions can change that state?

Examples:

```text
Submit project
Approve application
Join team
Send message
Create recommendation
Cancel order
```

These become the major backend operations.

---

## Question 3

# What rules control each action?

For every action:

```text
Who can do it?

When can they do it?

What must already be true?

What must never happen?
```

Example:

```text
Student can submit project
only when:
    project belongs to them
    required fields exist
    project is currently Draft
```

---

## Question 4

# What must happen together, and what can happen later?

Example:

```text
MUST HAPPEN TOGETHER

Create order
Reserve inventory
Record payment state
```

Maybe:

```text
CAN HAPPEN LATER

Send receipt
Update recommendations
Generate analytics
```

This determines transactions, background jobs, and system reliability.

---

## Question 5

# Where is the source of truth?

For every important fact:

```text
Where does it live?

Who owns it?

Who is allowed to change it?
```

Examples:

```text
User identity → authentication system

Order status → orders database

Product price → products database

AI explanation → recommendation record

Uploaded video → object storage
```

If students can answer these five questions, they can guide an AI coding agent far more effectively.

---

# What to ask a coding agent before allowing it to write code

A student should be able to give an agent a product action and say:

```text
Do not implement this yet.

First model the backend behavior.

Show me:

1. The system state involved in this action.

2. The state transition caused by the action.

3. The authoritative source of truth for each piece of data.

4. The request coming from the frontend.

5. Which information from the frontend is untrusted.

6. How the backend identifies the user.

7. Authorization rules.

8. Business rules that must be enforced.

9. The order in which backend operations happen.

10. Which operations must succeed atomically.

11. Possible concurrency problems if two users act at once.

12. Whether repeated requests could create duplicates.

13. Which work happens synchronously.

14. Which work should happen asynchronously.

15. Which actions are the core operation and which are side effects.

16. What persistent data changes.

17. What external services are involved.

18. Where AI is used and where deterministic logic should be used instead.

19. What happens when each dependency fails.

20. The final response returned to the frontend.

Call out any architectural decisions that I have not defined instead of silently inventing them.
```

This is much closer to how they should interact with coding agents.

---

# Main class exercise — Architect the backend before touching code

Give students a product:

```text
A group of friends wants to order food together.

Everyone can add items to the same cart.

One person eventually checks out.
```

Do not ask them to build anything.

Ask them to reason.

Start with:

```text
What is the state?
```

Possible answer:

```text
Group Order
Members
Cart Items
Restaurant
Payment
Order
```

Then:

```text
What can change?
```

```text
Member joins
Member adds item
Member removes item
Checkout begins
Cart locks
Payment succeeds
Order is submitted
```

Then introduce complexity.

### Situation 1

Someone adds food while another person is checking out.

What should happen?

Now they must define a rule.

---

### Situation 2

Two people press Checkout simultaneously.

What should happen?

Now they must think about concurrency.

---

### Situation 3

Payment succeeds but the restaurant API is temporarily unavailable.

What is the state of the order?

Now they must think about partial failure.

---

### Situation 4

The frontend sends:

```text
Total = $54.00
```

but menu prices now total:

```text
$61.00
```

Which total should be trusted?

Now they must think about source of truth.

---

### Situation 5

Payment request is retried twice.

Should the card be charged three times?

Now they must think about idempotency.

---

### Situation 6

The restaurant accepts the order, but sending the push notification fails.

Should the order disappear?

Now they must separate the core action from side effects.

---

### Situation 7

The group wants AI to recommend what to order.

Should AI be allowed to determine the final amount charged?

Obviously not.

Now they understand where AI fits.

This single exercise can carry much of the lecture because it exposes the actual architecture problems organically.

---

# The key lesson

By the end of Week 6, students should no longer think:

```text
Frontend = visible code

Backend = invisible code
```

They should think:

```text
Frontend
captures user intent.

Backend
controls system behavior.

Database
preserves system state.

External services
provide outside capabilities.

AI
provides probabilistic reasoning.

The backend coordinates all of them.
```

And when they use coding agents, their job is not to tell the agent:

```text
Build me a backend.
```

Their job is to define:

```text
What exists.

What can change.

Who can change it.

What rules control the change.

What information is trusted.

What must happen together.

What can happen later.

What happens when two things occur simultaneously.

What happens when something fails.

Where the truth lives.

Where AI is appropriate.

What the user receives at the end.
```

Once these decisions are clear, the agent can write code.

Without them, the agent is not implementing the student's product.

It is inventing one.
