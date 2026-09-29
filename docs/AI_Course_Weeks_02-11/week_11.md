# Week 13 — Your Code Works. Now Make It Survive Reality.

This should be the architecture lecture where everything finally becomes operational.

Until now, students have been thinking:

> I need a frontend.\
> I need a backend.\
> I need a database.\
> I need AI.\
> I need APIs.

Now change the question.

> **Where is every one of those things actually running?**

And then:

> **What happens when your computer is turned off?**

> **What happens when your backend restarts?**

> **What happens when 5,000 people arrive at once?**

> **What happens when the AI API stops responding?**

> **What happens when someone uploads a 2 GB video?**

> **What happens when your database password accidentally appears on GitHub?**

That is cloud architecture.

Not:

> “What is AWS?”

Not:

> “What is a server?”

The question is:

> **How do I take all the pieces I designed and make them operate as one real system?**

---

# The running example: something students would actually want to build

Imagine a group of students builds this:

# FRIDAY NIGHT

A platform for high school sports across Oklahoma.

During a football game, students can:

- upload photos and short video clips,
- see live scores,
- tag players,
- follow schools,
- receive game updates,
- ask AI for a game summary,
- generate highlight reels after the game.

During development, everything works beautifully.

One student runs the project.

Five friends open it.

They upload some videos.

The AI generates summaries.

Success.

Then Friday night arrives.

A championship game ends.

Someone posts the link on social media.

Ten thousand people open the platform.

Hundreds start uploading videos.

Everyone asks AI to summarize the game.

Now we find out whether they built:

> software that works

or

> a system that works.

That distinction should drive the entire lecture.

---

# Part 1 — The first question before deployment

Put this on the screen:

```text
YOUR PROJECT
```

Then ask:

> Where is it?

Students may say:

> GitHub.

No.

GitHub may contain the code.

That does not mean the application is running.

They may say:

> In Replit.

Maybe.

But is that your production environment?

They may say:

> On my computer.

Then nobody can use it when your computer is off.

The first important distinction is:

```text
CODE EXISTS
```

versus

```text
CODE IS RUNNING
```

versus

```text
PRODUCT IS OPERATING
```

These are three different things.

For a real product, several things have to be operating at the same time.

---

# Part 2 — Stop saying “deploy the app”

This is one of the most important habits students need when using coding agents.

Do not say:

> Deploy my app.

The application may contain completely different pieces.

For FRIDAY NIGHT:

```text
Frontend
Users see games, scores, clips

Backend
Receives uploads
Reads scores
Handles accounts
Calls AI

Database
Stores users
Schools
Games
Scores
Video metadata

File storage
Stores actual videos and photos

AI service
Generates game summaries

Background processing
Compresses video
Generates thumbnails
Creates highlights

Notifications
Sends score updates

External APIs
Maps
Messaging
Potential sports data
```

Deployment means answering this question for every piece:

```text
What is it?

Where will it run?

How will other pieces reach it?

What information does it need?

What happens if it stops?
```

That is the deployment architecture.

---

# Part 3 — The cloud is not one computer

Students often imagine:

```text
My computer
    ↓
Cloud
```

And somehow the cloud runs everything.

Break that idea.

A cloud product might actually look like this:

```text
                  USER'S PHONE
                       ↓
                    INTERNET
                       ↓
                FRONTEND HOST
                       ↓
                 BACKEND API
                  ↙    ↓    ↘
                 ↙     ↓     ↘
          DATABASE   STORAGE   AI API
                         ↓
                       QUEUE
                         ↓
                  VIDEO WORKER
                         ↓
                  NOTIFICATION
```

These pieces may be running on completely different machines.

Possibly in completely different companies.

The product works because they know how to communicate.

This is the final version of the Lego idea from the course:

The students are no longer just identifying pieces.

They are deciding:

> **Where each piece lives and how every connection works.**

---

# Part 4 — Frontend deployment

Start with the easiest piece.

The frontend is what reaches the user's browser.

For FRIDAY NIGHT:

```text
User opens:

fridaynight.app
```

The browser needs to receive:

```text
Pages
JavaScript
Styles
Images
Frontend components
```

Those files must live somewhere publicly reachable.

So:

```text
Browser
    ↓
Domain
    ↓
Frontend hosting
    ↓
Frontend loaded
```

Now introduce a very common failure.

The coding agent deploys the frontend.

Students celebrate.

They open the website.

It loads.

They click:

> Upload Video

Nothing happens.

Why?

Because the frontend is online.

But somewhere inside the frontend code is:

```text
http://localhost:8000/upload
```

Ask the class:

> Whose localhost?

The frontend is now running on the user's computer.

Their computer does not have the student's backend running on port 8000.

This is the first practical deployment lesson:

```text
DEVELOPMENT BACKEND

localhost:8000
```

must become something like:

```text
PRODUCTION BACKEND

api.fridaynight.app
```

The frontend needs to know:

> Where is my backend?

---

# Part 5 — The backend needs computation

Now follow one request.

A student uploads a football clip.

```text
Phone
 ↓
Frontend
 ↓
POST /videos
 ↓
Backend
```

The backend may need to:

```text
Check who the user is

Check file type

Check file size

Create a database record

Request an upload location

Start video processing

Return a response
```

That backend code has to be running somewhere continuously.

This is the role of cloud compute.

Students do not need to understand twenty infrastructure products.

They need to understand the major choices.

A backend might run as:

```text
A long-running application

A serverless function

A container

A group of containers
```

The important question is not:

> Which cloud buzzword should I use?

The important question is:

> What kind of work does my backend perform?

---

# Part 6 — Let the workload determine the architecture

Give them three very different backend jobs.

### Job A

```text
GET /game/123
```

Read one game.

Return the score.

Maybe 50 milliseconds.

---

### Job B

```text
POST /generate-summary
```

Send information to an AI model.

Wait 5–20 seconds.

Return a summary.

---

### Job C

```text
POST /upload-video
```

Take a 500 MB video.

Compress it.

Create three resolutions.

Extract audio.

Generate thumbnails.

Run AI analysis.

Potentially minutes of work.

These should immediately feel different.

That is the lesson.

Students should start recognizing:

```text
FAST REQUEST
```

versus

```text
SLOW JOB
```

versus

```text
HEAVY COMPUTATION
```

If everything is forced through the same backend request, the architecture becomes fragile.

The student should be able to tell the coding agent:

> The video processing may take several minutes. Do not run the entire process inside the user's upload request. Accept the upload, create a processing job, return immediately, and process the video asynchronously.

That is exactly the level of instruction they need to learn.

---

# Part 7 — Persistent things and disposable things

This should be one of the biggest ideas in the entire lecture.

Ask:

> I delete your backend server right now.

What should disappear?

Ideally:

```text
Nothing important.
```

The backend code can be restarted.

User accounts should still exist.

Game scores should still exist.

Videos should still exist.

This introduces one of the most important cloud distinctions:

```text
COMPUTE

Can often be restarted or replaced.
```

versus

```text
STATE

Must survive.
```

For FRIDAY NIGHT:

```text
Backend
Disposable

Database
Persistent

Video storage
Persistent
```

The system should be designed so that:

```text
Backend dies
    ↓
New backend starts
    ↓
Connects to same database
    ↓
Connects to same storage
    ↓
Product continues
```

Students using agents should understand why a line like this is dangerous:

```text
Save uploaded files to /uploads
```

If `/uploads` exists only inside the running backend machine, then:

```text
Backend replaced
    ↓
Videos gone
```

That is not a coding bug.

That is an architecture bug.

---

# Part 8 — Database and file storage are different

Now connect Weeks 7 and 9 to deployment.

Suppose a student uploads:

```text
state_championship_final_play.mp4
```

The actual 800 MB video belongs in file storage.

The database might store:

```text
video_id

user_id

game_id

filename

upload_time

processing_status

storage_location

thumbnail_location
```

So:

```text
DATABASE
Knows ABOUT the file
```

```text
OBJECT STORAGE
Contains the file
```

This distinction becomes critical at scale.

Imagine 50,000 videos.

You usually do not want your application database trying to behave like a giant video hard drive.

The student should be able to explain:

> Store the media itself in object storage. Store metadata and relationships in the database.

Now they can properly instruct an agent instead of just saying:

> Add video upload.

---

# Part 9 — How large platforms actually deliver media

Now make the example more interesting.

A student in Tulsa uploads a video.

Someone in Lawton watches it.

Someone in Oklahoma City watches it.

Ten thousand people replay the winning touchdown.

Should every viewer download the exact same file from the original storage location every time?

That would be slow and expensive.

Introduce the simplified idea of a CDN.

```text
Original video
      ↓
Object storage
      ↓
CDN caches copies closer to users
      ↓
Thousands of viewers
```

Students do not need to understand global networking internals.

They need the architecture intuition:

> Frequently requested large files should not necessarily travel through my backend every time.

This is important.

The backend should not normally do this:

```text
User
 ↓
Backend
 ↓
Backend downloads 500 MB video
 ↓
Backend sends 500 MB video
 ↓
User
```

Instead:

```text
User
 ↓
Frontend
 ↓
File/CDN URL
 ↓
Video delivered directly
```

The backend controls access.

The media system handles delivery.

That is how students start seeing real architecture.

---

# Part 10 — Background processing

Now return to the video upload.

The student uploads a video.

Bad architecture:

```text
Upload
 ↓
Wait
 ↓
Compress
 ↓
Wait
 ↓
Generate thumbnail
 ↓
Wait
 ↓
Run AI
 ↓
Wait
 ↓
Create highlight
 ↓
Finally respond
```

The user might wait five minutes.

Their browser closes.

The connection dies.

The entire operation may fail.

Better:

```text
User uploads video
       ↓
Video stored
       ↓
Database:
status = "processing"
       ↓
Backend adds job to queue
       ↓
Backend responds immediately
```

Then:

```text
Queue
 ↓
Worker picks up job
 ↓
Compress video
 ↓
Create thumbnail
 ↓
Run AI analysis
 ↓
Update database:
status = "ready"
```

The frontend can show:

```text
Uploading...

Processing...

Ready
```

Now explain:

### Queue

A list of work waiting to happen.

### Worker

A separate program performing that work.

This architecture appears everywhere.

Not just video.

```text
Generate a PDF

Send 5,000 emails

Process an Excel file

Analyze 200 documents

Create AI embeddings

Import public data

Generate a report
```

Students should begin asking:

> Does the user need to wait for this?

If no:

> Maybe it should be background work.

---

# Part 11 — Secrets: the deployment mistake that can cost actual money

Give them a realistic failure.

A student builds an AI feature.

Their frontend contains:

```text
AI_API_KEY = "..."
```

They publish the frontend.

Someone finds the key.

A script sends hundreds of thousands of requests.

Now the student receives the cloud bill.

This makes environment variables immediately relevant.

Students should understand:

```text
PUBLIC INFORMATION
```

can live in frontend code.

But:

```text
DATABASE PASSWORD

AI API KEY

EMAIL API KEY

PRIVATE SERVICE CREDENTIALS
```

must not.

The frontend should usually talk to:

```text
Frontend
 ↓
Backend
 ↓
AI provider
```

Not:

```text
Frontend
 ↓
AI provider
with secret key exposed
```

Teach them to tell the coding agent explicitly:

> Move all privileged API calls to the backend. Store production credentials in environment variables or managed secret storage. Never commit secrets to the repository and never expose them in frontend code.

That is a useful deployment instruction.

---

# Part 12 — Development is not production

Now introduce a dangerous scenario.

During development:

```text
User clicks
DELETE ALL GAMES
```

Developer laughs.

Reloads fake data.

No problem.

In production:

```text
User clicks
DELETE ALL GAMES
```

You may have just deleted the season.

Students need to understand that production changes the consequences.

A mature project may have:

```text
DEVELOPMENT

Fake data
Local services
Debugging enabled
Frequent changes
```

and

```text
PRODUCTION

Real users
Real data
Real credentials
Controlled changes
```

Possibly also:

```text
PREVIEW / STAGING
```

where new versions are tested before real users see them.

The critical rule:

```text
DEVELOPMENT
must not accidentally use
PRODUCTION DATA
```

Imagine an AI coding agent writing a test that deletes database rows.

That test must not run against the real production database.

Students should tell their agent:

> Verify that development, preview, and production use separate configuration and databases. Show me exactly how the application determines which environment it is running in.

That is architectural steering.

---

# Part 13 — The domain is only the front door

Students often think:

> I connected my domain. Deployment finished.

No.

The domain is simply how someone finds the product.

For example:

```text
fridaynight.app
```

may point to the frontend.

The frontend might call:

```text
api.fridaynight.app
```

The backend may connect privately to:

```text
Database

Object storage

Queue
```

The domain is only one connection in the architecture.

Ask students to draw:

```text
Publicly accessible
```

versus

```text
Private/internal
```

For example:

```text
PUBLIC

fridaynight.app

api.fridaynight.app
```

But the public internet should probably not directly access:

```text
Production database
```

This naturally introduces network boundaries without turning the class into a networking lecture.

---

# Part 14 — Now I break the product

This section should be interactive.

Show one failure at a time.

Ask:

> What happens?

---

## Failure 1

The backend restarts.

Should users lose their accounts?

No.

If they do, persistent information was stored in the wrong place.

---

## Failure 2

The AI provider is unavailable.

Does the entire sports platform stop working?

It should not.

Maybe:

```text
Scores still work.

Videos still work.

Game pages still work.

AI summaries temporarily unavailable.
```

This introduces graceful degradation.

Students should tell their agent:

> The AI feature is optional. If the AI service is unavailable, return the game information without the generated summary and show a clear temporary error.

---

## Failure 3

Someone uploads a 40 GB video.

What happens?

The system needs:

```text
File-size limits

File-type validation

Possibly direct uploads

Processing limits
```

This is architecture.

Not just UI.

---

## Failure 4

20,000 people watch the same highlight.

The database may be fine.

The backend may be fine.

Video delivery may become the bottleneck.

Different workloads stress different components.

---

## Failure 5

Every viewer automatically generates a new AI summary.

Now:

```text
20,000 viewers

20,000 AI requests
```

But the game summary is identical.

Why regenerate it 20,000 times?

Generate it once.

Store it.

Reuse it.

This teaches architecture and cost simultaneously.

---

# Part 15 — Cost is not something you discover after deployment

Show a bad architecture.

```text
Every page refresh
      ↓
Call AI
      ↓
Analyze same game again
```

Maybe each call costs very little.

But:

```text
1 user
cheap

100 users
still cheap

100,000 users
not cheap
```

The student should learn to identify:

```text
What runs once?

What runs per user?

What runs per request?

What runs per upload?

What runs every day?
```

Those questions reveal cost.

Students should tell their agent:

> Identify every operation that creates external API or compute cost. Estimate which operations grow with users, uploads, or traffic. Look for repeated work that can be cached or stored.

The goal is not cloud accounting.

The goal is understanding that:

> Architecture determines cost behavior.

---

# Part 16 — Scaling is finding the next thing that breaks

Do not explain scaling as:

> More users means bigger servers.

Instead, turn it into a game.

# LEVEL 1

```text
10 users
```

Everything works.

---

# LEVEL 2

```text
1,000 users
```

Still works.

---

# LEVEL 3

```text
50,000 users
```

What breaks?

Maybe:

```text
Backend cannot process requests fast enough.
```

Add more backend capacity.

Now what breaks?

```text
Database has too many connections.
```

Fix that.

Now what breaks?

```text
AI rate limit.
```

Fix that.

Now what breaks?

```text
Video-processing queue becomes 12 hours long.
```

Add workers.

Now what breaks?

```text
Cloud bill.
```

That is scaling.

Scaling is:

> As usage grows, find the next bottleneck.

Students should understand that architecture for:

```text
50 users
```

and

```text
50 million users
```

does not need to be identical.

In fact, designing a giant architecture for 50 users can be a mistake.

Complexity also has a cost.

Students should be comfortable telling their agent:

> We expect fewer than 500 initial users. Design the simplest architecture that is reliable at this scale. Explain what we would need to change if usage grows 100 times.

That is a much smarter instruction than:

> Make it scalable.

---

# Part 17 — Logs: reconstructing what actually happened

Now introduce a production complaint.

A user says:

> My video disappeared.

Without logs:

```text
???
```

With logs:

```text
20:14:02 Upload requested
20:14:03 User authenticated
20:14:04 Upload completed
20:14:04 Video record created: 8821
20:14:05 Processing job created
20:14:10 Worker started
20:14:14 ERROR: unsupported video codec
```

Now you have a story.

Logs are not random developer messages.

Logs let you reconstruct a journey through the architecture.

A useful request ID might connect:

```text
Frontend request

Backend request

Database operation

AI call

Background job
```

Students should learn a useful debugging habit:

> Do not immediately ask the agent to rewrite code.

First ask:

> Show me where the request failed.

Then fix that component.

---

# Part 18 — Monitoring: I do not want users to be my monitoring system

Bad production monitoring:

```text
Student emails:

"Hey, the website has been broken since yesterday."
```

Better:

The system already knows:

```text
Error rate increased

Backend stopped responding

Queue is growing

Database storage almost full

AI requests failing

Response time increased
```

Monitoring answers:

> Is the system healthy?

Logs answer:

> What happened?

Students do not need to build a giant operations platform.

But they should know to ask the agent:

> Add basic production health monitoring and error reporting. I need to know when the backend is unavailable or requests are repeatedly failing.

---

# Part 19 — Backups: simulate catastrophe

Ask:

> At 2:13 PM, someone accidentally deletes every game record.

At 2:14 PM, what do you do?

If the answer is:

> I don't know.

The deployment architecture is incomplete.

Backups create another recoverable copy of important information.

But make the lesson slightly deeper:

A backup that has never been tested may not actually save you.

Students should understand two questions:

```text
Do we have a backup?

Can we restore from it?
```

---

# Part 20 — The deployment map

At this point, give students the full system.

```text
                         USERS
                           ↓
                         DOMAIN
                           ↓
                    FRONTEND HOST
                           ↓
                      BACKEND API
              ↙            ↓             ↘
             ↙             ↓              ↘
        DATABASE      OBJECT STORAGE      AI API
                           ↓
                          CDN
                           ↓
                        VIEWERS


BACKEND
   ↓
QUEUE
   ↓
WORKERS
   ↓
VIDEO / AI PROCESSING
   ↓
DATABASE UPDATED
```

Now add the things that surround the system:

```text
Authentication

Permissions

Secrets

Logs

Monitoring

Backups

Cost controls

Error handling

Deployment environments
```

The students should finally see:

> These are not separate vocabulary words.

They are conditions required for the whole system to operate.

---

# Part 21 — How to actually work with the coding agent

This should be the centerpiece of the lesson.

Students should not give an agent one giant instruction:

> Deploy everything.

They should run a deployment conversation.

---

## Prompt 1 — Make the agent discover the system

> Inspect the entire project before making changes. Create an architecture inventory showing the frontend, backend, database, file storage, AI integrations, external APIs, authentication, scheduled jobs, and background processing. For each component, explain where it currently runs and what it depends on.

The student reviews it.

---

## Prompt 2 — Find development-only assumptions

> Search the project for anything that will fail outside the development environment. Check localhost URLs, local file paths, SQLite or temporary databases, hard-coded credentials, development-only CORS settings, local uploads, test accounts, and services that only run when the coding environment is open.

This is extremely valuable.

---

## Prompt 3 — State the real deployment constraints

The student gives the agent reality.

Example:

> This product will initially have 200–500 users. Users upload short videos and photos. Traffic may spike during major games. Video processing can happen asynchronously. We have a limited budget and should prefer the simplest managed architecture that is easy to operate.

Now the agent can make better decisions.

---

## Prompt 4 — Make the agent propose the architecture

> Propose the production architecture before deploying anything. For every component, show:
>
> - where it runs,
> - what connects to it,
> - what data it stores,
> - whether it is persistent,
> - whether it is public or private,
> - what secrets it needs,
> - what happens if it fails.

This forces architectural reasoning.

---

## Prompt 5 — Challenge the architecture

> Now act as a skeptical production engineer. Identify the five most likely ways this architecture could fail or lose data. Also identify the main security risk, scaling bottleneck, and cost risk.

Students should see that agents can critique their own proposed solutions.

---

## Prompt 6 — Create the deployment plan

> Create a step-by-step production deployment plan. Do not deploy yet. Show dependencies between steps and how we will verify each component before moving to the next one.

Possible plan:

```text
1. Production database

2. Object storage

3. Backend

4. Verify backend independently

5. Background worker

6. Verify job processing

7. Frontend

8. Connect frontend to production backend

9. Domain

10. Full end-to-end test

11. Monitoring

12. Backups
```

The exact order can vary.

The thinking should not.

---

# Part 22 — Students should understand configuration

An agent will often create variables like:

```text
DATABASE_URL

API_URL

AI_API_KEY

STORAGE_BUCKET

ENVIRONMENT
```

Students should not treat these as mysterious strings.

They should know:

```text
CODE
says WHAT it needs
```

```text
ENVIRONMENT
provides WHERE or WHICH one
```

For example:

Development:

```text
DATABASE_URL = development database
```

Production:

```text
DATABASE_URL = production database
```

Same code.

Different environment.

This is how one codebase can operate in different environments.

---

# Part 23 — The production verification challenge

After the agent says:

> Deployment successful.

The student should say:

> Prove it.

Run tests from the perspective of an actual user.

```text
Can I open the site from another device?

Can I create an account?

Can I log out and back in?

Does saved data remain?

Can I upload a file?

Can I access the file tomorrow?

Does the backend still work after restart?

Does a background job complete?

Does the AI integration work?

What happens when the AI fails?

What happens when an upload is invalid?

Are errors logged?

Are secrets hidden?

Is production using the production database?
```

A green deployment message means:

```text
The deployment command completed.
```

It does not necessarily mean:

```text
The system works.
```

Students must understand that difference.

---

# Part 24 — The three brutal tests

End with three tests that students can remember.

# TEST 1 — Kill the laptop

Close the coding environment.

Turn off the developer's computer.

Can the product still operate?

If not, something was never really deployed.

---

# TEST 2 — Kill the backend

Restart or replace the backend.

Does important information survive?

If not, state was stored in the wrong place.

---

# TEST 3 — Multiply reality by 100

Take:

```text
Users

Files

AI calls

Traffic

Data
```

Multiply everything by 100.

What breaks first?

That reveals the architecture's next bottleneck.

---

# Final mental shift

At the beginning of the course, a student sees:

```text
MY APP
```

After this lecture, they should see:

```text
                      USER
                       ↓
                    FRONTEND
                       ↓
                     NETWORK
                       ↓
                    BACKEND
                  ↙    ↓    ↘
                 ↙     ↓     ↘
           DATABASE   FILES   EXTERNAL SYSTEMS
                        ↓
                   BACKGROUND WORK
                        ↓
                       AI
```

And immediately ask:

```text
Where does each piece run?

Which pieces are temporary?

Which information must survive?

Which services are public?

Where are the secrets?

Which work should happen in the background?

What happens when a dependency fails?

How will we see errors?

What happens when usage grows?

What will cost money?

Can we recover the data?
```

That is the actual goal of Week 13.

Not to turn high school students into cloud engineers.

It is to make them capable of looking at an AI-generated application and saying:

> I understand what this system is made of.

> I understand where each part needs to live.

> I understand what must remain persistent.

> I understand which parts should be separated.

> I understand what the agent is proposing.

> I understand enough to challenge it when the architecture makes no sense.

By this point, the agent should no longer be driving the project.

The student should be driving the architecture.

The agent is just doing the implementation.
