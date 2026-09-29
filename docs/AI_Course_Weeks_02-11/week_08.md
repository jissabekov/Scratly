# Week 8 — Your Product Does Not Live Alone

## APIs, integrations, and how systems communicate with other systems

### The central question

By this point, students understand:

**Week 7:**\
How does my product organize and retrieve the structured information it owns?

Students\
Organizations\
Projects\
Applications\
Statuses\
Relationships\
Queries\
Databases

Now introduce the next problem:

> What happens when your product needs something that exists outside your product?

Maybe you are building an application that needs to:

- Know where an address is on a map
- Check tomorrow's weather
- Let someone log in with Google
- Send a text message
- Send an email
- Process a payment
- Ask an AI model a question
- Retrieve information from a school system
- Verify an address
- Get live sports scores
- Look up public government data

You could theoretically build every one of these capabilities yourself.

But you probably should not.

This is where **system integration** begins.

The key lesson is not:

> "An API lets applications talk."

That is technically correct, but architecturally almost useless.

The useful lesson is:

> **Modern products are assembled from systems that own different capabilities and different information. Architecture is deciding where your product ends, where another system begins, and how information safely moves between them.**

---

# The hook: Could you actually build Uber?

Start the lecture with a familiar product.

Ask:

> "Suppose I give you an AI coding agent and tell you to build Uber. What would you actually have to build?"

Students will probably think:

- Driver app
- Rider app
- Map
- Booking screen

Keep going.

The product also needs:

- Maps
- GPS coordinates
- Address search
- Route calculation
- Payment processing
- Credit card handling
- Identity verification
- SMS
- Push notifications
- Email
- Fraud detection
- Customer support
- Cloud infrastructure

Then ask:

> "Does Uber need to personally build every one of those technologies?"

No.

A product can combine capabilities from many systems.

Visually:

```text
                    ┌──────────────┐
                    │ Mapping      │
                    │ System       │
                    └──────▲───────┘
                           │
                           │
┌──────────┐       ┌───────┴────────┐       ┌──────────────┐
│  User    │──────▶│   Your Product │──────▶│ Payment      │
└──────────┘       └───────┬────────┘       │ System       │
                           │                └──────────────┘
                  ┌────────┼─────────┐
                  │        │         │
                  ▼        ▼         ▼
              Database    AI      Messaging
              you own   Service     Service
```

Now the students can see the architectural problem.

Your product is not necessarily one giant piece of software.

It is a **system that coordinates other systems**.

---

# Part 1 — Where does your product end?

Before talking about APIs, introduce the idea of a **system boundary**.

Suppose a student builds:

### Community Opportunity Finder

Students create profiles and find volunteer opportunities near them.

From Week 7, the product might own:

```text
Students
Organizations
Opportunities
Applications
Saved Opportunities
```

Those belong in the application's database.

But now the student wants:

> "Show opportunities within 20 miles of me."

The database contains:

```text
Address:
123 Main Street
Norman, Oklahoma
```

But calculating geographic coordinates and routes is a completely different capability.

The product could send the address to a mapping system.

```text
Your Product

"123 Main Street, Norman, OK"
        │
        ▼
External Mapping System
        │
        ▼
35.22 latitude
-97.44 longitude
```

Now the product can save those coordinates and use them.

This introduces an important architecture question:

> **Who owns which responsibility?**

Your application owns:

- The student's profile
- The opportunity
- Whether the student saved it

The mapping provider owns:

- Address interpretation
- Geographic coordinates
- Mapping data

That division is the **system boundary**.

---

# Part 2 — An API is a contract across that boundary

Now introduce the API.

An API is not another mysterious software component.

It is a **defined agreement for communicating with another system**.

Imagine telling another system:

```text
I will send you:

Street: 123 Main Street
City: Norman
State: Oklahoma
```

The system promises:

```text
If the request is valid,
I will return:

Latitude: 35.22
Longitude: -97.44
```

That agreement is the API contract.

Students should understand five parts.

```text
REQUEST
What am I asking you to do?

INPUT
What information do you need from me?

AUTHENTICATION
How do you know I am allowed to ask?

RESPONSE
What will you send back?

FAILURE
What will you tell me if something goes wrong?
```

This is much more useful when guiding an agent than simply saying:

> "Add the Google Maps API."

---

# Part 3 — What actually travels between systems?

Connect directly back to Week 4.

Students already learned:

```text
Request
    ↓
Network
    ↓
Server
    ↓
Response
```

Now show them that the same thing happens **between servers**.

```text
Student
   │
   ▼
Frontend
   │
   │ "Find opportunities"
   ▼
Your Backend
   │
   │ "Where is this address?"
   ▼
Mapping API
   │
   │ latitude + longitude
   ▼
Your Backend
   │
   │ query database
   ▼
Your Database
   │
   ▼
Your Backend
   │
   ▼
Frontend
```

One button click may cause communication between several systems.

This is the key mental model.

The student sees:

```text
[ Find Opportunities ]
```

But underneath:

```text
User Action
   ↓
Frontend Request
   ↓
Backend
   ↓
External System
   ↓
Database Query
   ↓
Possibly Another External System
   ↓
Backend Decision
   ↓
Response
   ↓
Screen
```

This is why architecture matters.

---

# Part 4 — What does an API request actually look like?

Do not turn this into an HTTP programming lecture.

Students only need enough detail to recognize what their coding agent is creating.

Show something like:

```text
POST https://api.example.com/analyze
```

Then:

```json
{
  "text": "I want to volunteer with animals."
}
```

And perhaps the response:

```json
{
  "category": "animal_welfare",
  "confidence": 0.93
}
```

Explain:

### Endpoint

```text
/api/analyze
```

The location representing a capability.

### Operation

```text
GET
POST
PUT
DELETE
```

Roughly:

```text
GET     Give me information
POST    Do something or create something
PUT     Update something
DELETE  Remove something
```

They do not need to memorize HTTP specifications.

They need to be able to look at agent-generated code and understand:

> "This code is sending information outside my system and expecting something back."

### Parameters or request body

The information being sent.

### Response

The information returned.

### Status or error

Whether the request succeeded.

### JSON

A common structured format for information moving between systems.

Connect this directly to Week 7.

A database might contain:

```text
Student
- id
- name
- interests
```

An API may send:

```json
{
  "student_id": 142,
  "interests": ["sports", "education"]
}
```

Same information.

Different purpose.

The **database stores it**.

The **API transports it**.

That distinction should become very clear.

---

# Part 5 — APIs are only one way systems communicate

This is where I would go beyond the original Week 8.

Students should understand that "integration" is bigger than "API."

There are several common patterns.

---

## Pattern 1: Ask and wait

### Request → Response

Your system asks another system something.

```text
Your System
    │
    │ What's the weather tomorrow?
    ▼
Weather Service
    │
    │ 82°F, rain
    ▼
Your System
```

Common for:

- AI calls
- Maps
- Search
- Weather
- Looking up information

The user may be waiting for the answer.

This is usually called **synchronous communication**.

Conceptually:

> "I cannot finish my work until you answer."

---

## Pattern 2: Tell me when something happens

Sometimes constantly asking is inefficient.

Imagine your product needs to know when a payment succeeds.

One design would be:

```text
Did it finish?
No.

Did it finish?
No.

Did it finish?
No.

Did it finish?
Yes.
```

Instead, the payment service can tell your system:

```text
Payment completed.
```

This is a **webhook**.

Conceptually:

> "Here is an address. Send me a message when something happens."

```text
Payment Service
      │
      │ Event: Payment Completed
      ▼
Your Backend
      │
      ▼
Update Database
```

Students do not need to implement complex webhook infrastructure during the lecture.

But they should know this pattern exists.

It changes architecture.

---

## Pattern 3: Check occasionally

Imagine you need data from another organization, but it does not notify you automatically.

Your system might check:

```text
Every night at 2:00 AM:

Get new opportunities.
```

This is a **scheduled synchronization**.

```text
External System
       ▲
       │ Every night
       │
Your Backend
       │
       ▼
Your Database
```

The information may now be several hours old.

Which introduces:

### Data freshness

How current does the information need to be?

Weather:

Maybe minutes.

Organization directory:

Maybe once per day.

School enrollment status:

Maybe once per night.

Historical census data:

Maybe once per year.

There is no universal answer.

The product architect decides.

---

## Pattern 4: Exchange a large batch of data

Not every organization has a beautiful real-time API.

Sometimes another organization gives you:

```text
students.csv
```

or:

```text
organizations.xlsx
```

or:

```text
daily_export.json
```

Your system imports it.

This is still **system integration**.

It just uses a file instead of a live API.

This is an important lesson for students working with real nonprofits, schools, or government organizations.

Real systems are often messy.

They may say:

> "We can email you a spreadsheet every Friday."

Your architecture still needs to handle that.

This also creates the transition into Week 9:

> What happens when what you receive is not a neat table, but 50,000 PDFs, photographs, reports, or videos?

That becomes the next lesson.

---

# Part 6 — The most important architecture decision: Do I call it every time?

Consider the mapping example.

Suppose your database contains 10,000 organizations.

Every time a student searches, you could send all 10,000 addresses to a mapping API.

That would be absurd.

Instead:

```text
Organization created
        ↓
Send address to Maps API
        ↓
Receive latitude / longitude
        ↓
Store coordinates in database
```

Later:

```text
Student searches
        ↓
Query stored coordinates
        ↓
Return nearby organizations
```

Now introduce a major architectural idea:

> **External systems can provide information without becoming your permanent source of truth for everything.**

Sometimes you:

```text
CALL → USE → DISCARD
```

Sometimes:

```text
CALL → SAVE RESULT → REUSE
```

Sometimes:

```text
CALL → CACHE TEMPORARILY → REFRESH LATER
```

Students should learn to ask:

> Will this information change?

> How expensive is it to retrieve?

> How often will I need it?

> How fresh must it be?

This connects directly to Week 7's discussion of database design and query efficiency.

---

# Part 7 — Never confuse your system's truth with another system's truth

Suppose your application displays:

```text
Student enrollment status: ACTIVE
```

But that information originates from the school's official system.

Which system is the real source of truth?

Probably the school system.

Your application may have a copy:

```text
ACTIVE
Last synchronized: July 17
```

But the authoritative information exists somewhere else.

This creates two concepts.

### Source of truth

The system that officially owns the information.

### Local copy

Information copied into your system for speed, convenience, or analysis.

Now students should see a connection:

```text
External System
Source of Truth
      │
      │ Synchronization
      ▼
Your Database
Local Copy
```

The architect must decide:

> What happens when the two disagree?

That is a real system-design question.

---

# Part 8 — External systems fail

This should be one of the biggest parts of the lecture.

When students use agentic coding, agents can easily create something that works perfectly during a demo.

Real architecture asks:

> "What happens on the bad day?"

Suppose:

```text
User clicks:
Analyze My Essay
```

Your backend calls an AI API.

Normally:

```text
AI responds in 3 seconds.
```

But today:

```text
AI responds in 45 seconds.
```

Or:

```text
AI API unavailable.
```

Or:

```text
You exceeded your usage limit.
```

Or:

```text
Your API key expired.
```

The product needs a plan.

Teach students to think about:

### Timeout

How long are we willing to wait?

### Retry

Should we try again?

### Fallback

Can the product continue without this service?

### Error state

What should the user see?

### Logging

How will we know what failed?

The most important mindset:

> An external integration is a dependency you do not control.

Your code may be perfect.

The product can still fail.

---

# Part 9 — Be careful with retries

Give students an interesting example.

Your system asks an AI API:

```text
Analyze this paragraph.
```

The request fails.

Trying again is probably fine.

Now imagine:

```text
Charge this person's card $50.
```

The connection disappears before your system receives the response.

Did the payment happen?

Maybe.

If the agent blindly retries:

```text
Charge $50 again.
```

Now you may have charged $100.

This is where the Week 6 concept of **idempotency** becomes real.

The basic idea:

> Design operations so that accidentally repeating the same request does not accidentally perform the action twice.

Students do not need to implement payment infrastructure.

They need to learn the question:

> "What happens if this request is accidentally sent twice?"

That is exactly the kind of question they should ask an agent.

---

# Part 10 — Speed: every external call adds waiting

Consider a feature that does this:

```text
Call Service A: 2 seconds
        ↓
Call Service B: 3 seconds
        ↓
Call AI: 5 seconds
        ↓
Call Service C: 2 seconds
```

If everything waits sequentially:

```text
2 + 3 + 5 + 2 = 12 seconds
```

The product feels slow.

Students should understand:

> Architecture affects how long users wait.

Possible solutions include:

- Avoid unnecessary calls
- Save reusable results
- Cache information
- Run independent requests at the same time
- Move slow work into the background

They do not need to master parallel programming.

They need to recognize the architectural question:

> Does the user need to wait for this operation to finish?

For example:

```text
Create account
    ↓
Save account
    ↓
Show success immediately
    ↓
Send welcome email in background
```

The user does not need to stare at a loading screen while an email server works.

---

# Part 11 — API limits and cost

Now introduce a reality students will immediately understand.

APIs are often not unlimited.

A provider may say:

```text
1,000 requests per day
```

or:

```text
$0.002 per request
```

or:

```text
100 requests per minute
```

This is a **rate limit** or usage limit.

Imagine an agent builds:

```text
Every time the user moves the mouse:
Call AI API.
```

Technically it works.

Architecturally it is terrible.

A student should ask:

```text
How often will this API be called?
        ×
How many users?
        ×
How much does each call cost?
```

A tiny architecture decision can become a huge cost at scale.

```text
1 user
× 10 calls
= 10 calls
```

versus:

```text
100,000 users
× 10 calls
= 1,000,000 calls
```

This connects directly to the scale thinking introduced in Week 7.

---

# Part 12 — Authentication is not authorization

Now explain how systems know who is communicating.

### API key

Essentially:

> "This request came from application X."

The key should normally live on the backend.

Not:

```text
Browser
   │
   │ Secret API Key
   ▼
External Service
```

Because users may be able to inspect it.

Instead:

```text
Browser
   │
   ▼
Your Backend
   │
   │ Secret API Key
   ▼
External Service
```

Then introduce, without excessive detail:

### OAuth

Used when one application needs permission to access another system **on behalf of a user**.

For example:

```text
"Allow this application to access your Google Calendar?"
```

The user grants limited permission.

The application should not receive the user's Google password.

Students only need the conceptual distinction:

```text
API Key:
Who is the application?

User Login:
Who is the user?

Authorization:
What is this user/application allowed to do?
```

---

# Part 13 — Data crossing the boundary creates privacy risk

Suppose your application sends this to an AI service:

```text
Please summarize this student's counseling record.
```

Technically, the API integration may work perfectly.

Architecturally and ethically, it may be unacceptable.

Every external integration creates another question:

> What information leaves my system?

Teach **data minimization**.

Instead of sending:

```text
Student Name
Home Address
Phone Number
Student ID
Full School Record
Essay
```

when only the essay is required, send:

```text
Essay
```

Ask:

> Does the external service actually need this information?

This should become automatic architecture thinking.

---

# Part 14 — APIs change

Imagine the API response today is:

```json
{
  "temperature": 82
}
```

Your application expects:

```text
temperature
```

Next year the provider changes it to:

```json
{
  "temperature_fahrenheit": 82
}
```

Your code may break.

This introduces:

### API versions

For example:

```text
/v1/weather
/v2/weather
```

And the broader lesson:

> When you depend on another system, changes to that system can affect your product.

A production system needs to know:

- Which external systems it depends on
- Which versions it uses
- What happens when responses change
- How failures are detected

---

# Part 15 — The real architectural decision: Build, borrow, or connect?

Now bring everything together.

Suppose a student needs AI summarization.

Option A:

```text
Build and host your own AI model.
```

Option B:

```text
Use an external AI API.
```

Suppose they need geographical coordinates.

Option A:

```text
Build your own worldwide mapping database.
```

Option B:

```text
Use a mapping provider.
```

The decision involves:

```text
BUILD
More control
More engineering
More infrastructure
You own the problem

BORROW / API
Faster to build
Less infrastructure
Possible cost
External dependency
Less control

IMPORT / SYNCHRONIZE
Useful when real-time access is unnecessary
Can work with older systems
Data may become stale
You must manage synchronization
```

Architecture is deciding:

> Which capabilities are important enough for us to own?

and:

> Which capabilities should we obtain from somewhere else?

---

# The main classroom challenge

## "Architect One Button"

Give students this feature:

> A student uploads a project idea.\
> The system evaluates it with AI.\
> It checks whether similar community organizations exist nearby.\
> It saves the project.\
> It emails the student when the analysis is complete.

Ask them to architect what happens after the student presses:

```text
[ Analyze My Project ]
```

A strong answer might become:

```text
Student
   │
   ▼
Frontend
   │
   │ project text
   ▼
Backend
   │
   ├──────────────▶ Database
   │                Save project
   │
   ├──────────────▶ AI API
   │                Analyze project
   │
   ├──────────────▶ Mapping API
   │                Resolve location
   │
   ▼
Database
Save analysis
   │
   ▼
Email Service
Send completion notification
```

Then make them answer:

### 1. What does our system own?

```text
Student
Project
Analysis result
Project status
```

### 2. What does another system own?

```text
AI capability
Mapping information
Email delivery
```

### 3. Which communication is request/response?

```text
AI analysis
Mapping lookup
```

### 4. What can happen in the background?

```text
Email
Possibly long AI analysis
```

### 5. What happens if the AI service fails?

The project should still exist.

Perhaps:

```text
status = ANALYSIS_FAILED
```

The student can retry.

### 6. What information is allowed to leave our system?

Do we need to send:

```text
Student name?
Address?
Student ID?
```

Maybe not.

### 7. What is our source of truth?

The project's saved state belongs in our database.

Not inside the AI provider.

This one exercise brings together Weeks 4, 6, 7, and 8.

---

# What students should say to a coding agent

By the end of Week 8, students should recognize that this is a bad instruction:

> "Add OpenAI and Google Maps."

A much stronger architectural instruction is:

```text
We need two external integrations.

1. Mapping service

When an organization is created or its address changes,
send the address to the mapping API and retrieve latitude and longitude.

Store the coordinates in our database so we do not call the API
every time someone searches.

The API key must remain on the backend.

If geocoding fails, save the organization but mark its location
as unresolved.

2. AI service

When a student submits a project description,
send only the project text to the AI API.

Do not send the student's name, email, or other profile information.

The analysis may take several seconds, so design the UI with
loading and failure states.

Save the AI result in our database so it can be retrieved later
without generating it again.

Before implementing, explain:

- the request sent to each external system
- the expected response
- where authentication is stored
- which data is persisted
- expected API costs and rate limits
- timeout and retry behavior
- what happens when each service is unavailable
```

Now the coding agent has an architecture to implement instead of permission to invent one.

---

# The Week 8 Integration Canvas

For every external system, students should be able to fill this out:

```text
EXTERNAL SYSTEM:
What system are we connecting to?

PURPOSE:
Why do we need it?

DIRECTION:
Are we asking it for something,
or is it sending events to us?

TRIGGER:
What causes the communication?

INPUT:
What information leaves our system?

OUTPUT:
What comes back?

AUTHENTICATION:
How are we allowed to access it?

SOURCE OF TRUTH:
Who officially owns the information?

STORAGE:
Do we save the result, cache it, or discard it?

FRESHNESS:
How current must the information be?

SPEED:
Does the user have to wait?

FAILURE:
What happens when the system is unavailable?

RETRY:
Is repeating the request safe?

LIMITS:
Are there rate limits or usage limits?

COST:
What happens when usage grows 100×?

PRIVACY:
Are we sending information the external system does not need?
```

Students do not need perfect answers.

They need to learn that these questions exist.

---

# The 60-minute structure

## 0–5 min — "Could you actually build Uber?"

Expose how many outside capabilities sit behind one familiar product.

Introduce:

> Your product has boundaries.

---

## 5–12 min — Your system versus other systems

Use the Community Opportunity Finder.

Separate:

```text
Our database
Our backend
External systems
```

Introduce ownership and system boundaries.

---

## 12–20 min — What actually crosses the boundary?

Build on Week 4:

```text
Request → External System → Response
```

Show endpoint, operation, JSON, response, error.

Introduce API contract.

---

## 20–30 min — Four ways systems exchange information

Teach:

```text
Request / Response
Webhook
Scheduled synchronization
Batch/file import
```

Focus on when each pattern makes sense.

---

## 30–42 min — Architecture problems that appear because the system is external

Fast sequence:

```text
Latency
Timeouts
Retries
Duplicate actions
Caching
Rate limits
Cost
Data freshness
API changes
```

The main question throughout:

> "What happens when this works for 10 users versus 100,000 users?"

---

## 42–48 min — Security and trust boundaries

Explain:

```text
API keys
Backend secrets
OAuth concept
Authentication
Authorization
Data minimization
```

Especially:

> Never automatically send all available user information to an external service.

---

## 48–57 min — Architect One Button challenge

Students design:

```text
[ Analyze My Project ]
```

They identify:

- Internal systems
- External systems
- Calls
- Data movement
- Storage
- Background work
- Failures

---

## 57–60 min — The architecture rule

Finish with one diagram:

```text
                 WEEK 7
        What information do we own?
                    │
                    ▼
              OUR DATABASE
                    │
                    │
                    ▼
                 WEEK 8
     What must we get from or send to
             OTHER SYSTEMS?
                    │
                    ▼
        APIs / Webhooks / Sync
                    │
                    ▼
                 WEEK 9
     What happens when the information
       becomes documents, images,
         video, audio, and large
          searchable collections?
```

And leave them with one rule:

> **Do not tell your coding agent, "Connect this API."**

Tell it:

> **What system are we connecting to, why are we connecting to it, what crosses the boundary, who owns the truth, what gets saved, and what should happen when the connection fails?**

That is the level at which they begin to **architect a product with an agent rather than simply ask an agent to generate code**.
