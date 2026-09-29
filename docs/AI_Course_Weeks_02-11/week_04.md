# Week 4 — The Invisible Conversation Behind Every Tap

## Opening question

Two students are buying the **last available concert ticket**.

They both see:

> 1 ticket remaining

They both press **Buy** at almost exactly the same time.

Who gets it?

The answer cannot be decided by either student’s screen. Both screens believe the ticket is available. A remote system must receive both messages, decide which arrived first, reserve the ticket once, reject the second request, and send different answers back.

This is why applications need the internet, servers, requests, responses, validation, and a shared source of truth.

The central lesson is not:

> “The browser sends a request to a server.”

The central lesson is:

> **Every important action in an online product is a conversation between systems, and the product designer must define that conversation.**

---

# The architectural picture

Students should already understand that a product contains different pieces:

- Interface
- Computation
- Storage
- External services
- AI
- Users

This week explains how those pieces communicate when they are located on different computers.

```text
A user does something
        ↓
The interface turns the action into a message
        ↓
The message travels through a network
        ↓
A remote system receives it
        ↓
The remote system checks whether it is valid
        ↓
It reads data, changes data, or performs computation
        ↓
It creates a response
        ↓
The response travels back
        ↓
The interface decides what to show
```

The screen is only the visible edge of this conversation.

---

# What students must be able to do after this lecture

By the end of Week 4, a student should be able to describe a feature using questions such as:

- What exactly causes the message to be sent?
- Which information leaves the device?
- Where is it sent?
- Who is allowed to send it?
- What must the server verify?
- Where does the server get the answer?
- What information comes back?
- What happens while the user waits?
- What happens if the request is sent twice?
- What happens if the internet disconnects?
- Which system owns the correct version of the information?

These are the questions that help a coding agent build a real product instead of a convincing-looking fake interface.

---

# 0–7 minutes — The last-ticket problem

Begin with the concert-ticket situation.

Put this on the screen:

```text
LAST TICKET

Student A sees: Available
Student B sees: Available

Student A presses Buy
Student B presses Buy
```

Ask the class:

1. Can both browsers decide who wins?
2. Can the ticket be stored only inside Student A’s browser?
3. What happens if one student presses Buy twice?
4. What happens if payment succeeds but the confirmation page fails to load?
5. What happens if the internet disconnects after the click?

Let students argue about it.

Then reveal the core problem:

> Each device knows only part of what is happening.

Student A’s browser does not know what Student B is doing. Student B’s browser does not know whether the ticket has already been reserved. The system needs a computer that both students communicate with.

That computer acts as the server.

```text
Student A’s browser ─┐
                     ├──→ Ticket server ──→ Ticket database
Student B’s browser ─┘
```

The ticket server decides:

- Is the ticket still available?
- Is this user signed in?
- Has this request already been processed?
- Can the payment be accepted?
- Should the ticket now be marked unavailable?
- What response should each student receive?

## First architecture principle

> When multiple users share or compete for the same information, the browser cannot be the final authority.

The shared system must own the truth.

---

# 7–14 minutes — What actually leaves the device?

Students often imagine that pressing a button sends the entire screen somewhere.

It does not.

The application creates a message containing selected information.

For the ticket example, the message might mean:

```text
User 1847 wants to reserve ticket 9082
for the 8:00 PM concert.
```

The real message may contain information such as:

```json
{
  "ticketId": "9082",
  "eventId": "concert-441",
  "quantity": 1,
  "requestId": "purchase-attempt-7719"
}
```

Students do not need to memorize JSON.

They need to understand why the information has names.

Without structure, the server might receive:

```text
9082, 441, 1, 7719
```

What does each number mean?

Structured messages allow both systems to agree:

- This value identifies the ticket
- This value identifies the event
- This value is the quantity
- This value identifies this specific attempt

## Explain payload

The information carried inside a request is often called the **payload**.

A payload might contain:

- Form answers
- Search filters
- A message
- A location
- An image
- A video
- An item identifier
- Instructions for an AI model

## Agent-development lesson

When students tell an agent:

> “Send the form to the backend,”

the agent still has to guess:

- Which fields?
- What should they be called?
- Which are required?
- Which are optional?
- What format should dates use?
- Should the image be included?
- Should the user’s location be included?
- Should empty answers be sent?
- How will the server identify the user?

A better instruction is:

```text
When the user submits the form, send:

- project title
- selected category
- county
- short description
- contact preference
- optional image identifier

Do not send fields that exist only for display.
Require title, category, county, and description.
```

The student does not need to write the networking code.

The student must define the message.

---

# 14–20 minutes — How the message knows where to go

Use a URL that looks like something from a real application:

```text
https://api.stagepass.app/events/441/tickets/9082/reserve
```

Break it apart.

## `https://`

This identifies the communication rules.

HTTPS also protects information while it travels between the device and the remote system.

Students do not need to study encryption protocols. They should understand:

> Information sent through a product should not travel as openly readable traffic.

## `api.stagepass.app`

This is the domain name.

A domain is a human-readable name connected to a destination on the internet.

The browser uses a system called DNS to discover which network address is connected to that name.

Conceptually:

```text
api.stagepass.app
        ↓
Which network address belongs to this domain?
        ↓
Send the message to that destination
```

## `/events/441/tickets/9082/reserve`

This is the path.

It identifies the part of the system the application wants to use.

```text
/events
/events/441
/events/441/tickets
/events/441/tickets/9082
/events/441/tickets/9082/reserve
```

The path becomes more specific as it continues.

## Endpoint

A specific address through which another part of the application can request something is often called an **endpoint**.

An endpoint is not just “where the server is.”

It represents a particular capability:

```text
/reserve
/cancel
/upload
/generate
/login
/messages
/notifications
```

## Agent-development lesson

An agent may create an endpoint called:

```text
/saveData
```

That is vague.

Save which data? For what user? Under which rules?

Clear endpoints encourage clear architecture:

```text
POST /tournaments/88/matches/14/report-result
GET /users/42/notifications
POST /videos/processing-jobs
DELETE /playlists/19/tracks/73
```

Students should be able to tell whether the system’s capabilities are understandable from its structure.

---

# 20–27 minutes — A request is not automatically trusted

This is one of the most important concepts for students using coding agents:

> The server should not trust information simply because the browser sent it.

A browser could send:

```json
{
  "ticketId": "9082",
  "price": 1
}
```

The ticket does not cost one dollar merely because the request says so.

The server should retrieve the real price from its own database.

A student might change a value accidentally. Someone else may intentionally manipulate it. The frontend may contain an old price. The browser might resend an outdated request.

The server must validate the request.

## Validation questions

For the ticket purchase, the server should check:

- Does this ticket exist?
- Is it still available?
- Is the event still active?
- Is the requested quantity allowed?
- Is the user signed in?
- Is the user permitted to purchase it?
- Has the request already been completed?
- Does the server’s stored price match the transaction?

## Authentication

Authentication answers:

> Who is this user?

Examples:

- Signed-in account
- Session
- Login token
- School account

## Authorization

Authorization answers:

> Is this user allowed to perform this action?

A student may be authenticated but still not authorized to:

- Change another student’s profile
- View private teacher notes
- Delete an organization
- Approve their own project
- Edit another team’s score

## Catchy rule

> **Authentication checks the name tag. Authorization checks the permission.**

## Agent-development lesson

A weak prompt says:

```text
Only show the Delete button to administrators.
```

That is not enough.

Hiding a button is interface behavior, not security.

A better instruction says:

```text
Only administrators may delete a tournament.

Hide the Delete button for other users, but also enforce the administrator check on the server. Reject unauthorized requests even if someone sends the request manually.
```

---

# 27–41 minutes — Five ways products communicate

Not every feature should use the same type of network interaction.

Students need to recognize the pattern before asking an agent to build it.

---

## Pattern 1 — Request one thing and receive one answer

### Example: Open a Spotify album

The application asks:

> Give me the album information and its first group of tracks.

The response returns:

- Album title
- Artist
- Cover image location
- Release year
- First 20 tracks

Why not return every track, every comment, every listener, and every related artist?

Because retrieving unnecessary information makes the product slower and more expensive.

## Pagination

Applications often retrieve information in smaller groups.

```text
Give me the first 20 tracks
        ↓
User scrolls
        ↓
Give me the next 20 tracks
```

This is called pagination.

## Agent instruction

Instead of:

```text
Load all activity records.
```

Use:

```text
Load the newest 25 activity records.

When the user reaches the bottom, request the next 25.
Do not download the entire history when the page first opens.
```

---

## Pattern 2 — Send a command that changes shared information

### Example: Equip an item in an online game

The player equips a new item.

The device sends:

```text
Equip item 712 in the character’s helmet slot.
```

The server checks:

- Does the player own item 712?
- Is it actually a helmet?
- Can it be used by this character?
- Is the account currently banned or restricted?
- What item was equipped before?
- Should this change appear on the player’s other device?

The server stores the change and responds with the confirmed loadout.

## Source of truth

The server’s saved loadout should normally be the source of truth.

Otherwise, the player could equip a paid item simply by changing information inside the browser.

## Agent instruction

```text
When the player equips an item:

1. Send the item ID and slot name.
2. Verify ownership on the server.
3. Verify that the item can be used in that slot.
4. Save the confirmed loadout.
5. Return the complete updated loadout.
6. Update the interface using the server’s response, not only the original click.
```

---

## Pattern 3 — Upload a large file

### Example: Upload a 60-second video

A video is not the same as a small form message.

It may contain millions of bytes and take noticeable time to upload.

The product needs to consider:

- Upload progress
- File size
- File format
- Connection loss
- Resuming or restarting
- Storage location
- Processing after upload
- Thumbnail creation
- Multiple video resolutions

A simplified workflow:

```text
User chooses video
        ↓
Application checks file type and size
        ↓
Video uploads to file storage
        ↓
Storage confirms receipt
        ↓
A processing job begins
        ↓
The system creates a thumbnail
        ↓
The system creates smaller versions
        ↓
The video becomes ready
```

The first response may not contain the finished video.

It may contain:

```json
{
  "uploadAccepted": true,
  "videoId": "video-781",
  "status": "processing"
}
```

## Agent instruction

A weak instruction:

```text
Add video upload.
```

A useful instruction:

```text
Allow MP4 and MOV files up to 200 MB.

Show upload progress.
Do not mark the video as published immediately after upload.
Create a processing state.
Show “Processing video” until the server reports that the thumbnail and playable version are ready.
Preserve the draft if processing fails.
```

---

## Pattern 4 — Start work that finishes later

### Example: Generate an AI image

AI work may take several seconds or longer.

Keeping one browser request open indefinitely can create problems.

Instead, the application may create a job.

```text
Create an image from this prompt
        ↓
Server creates job 552
        ↓
Server responds: job accepted
        ↓
AI system performs the work
        ↓
Application checks the job status
        ↓
Finished image becomes available
```

Initial response:

```json
{
  "jobId": "552",
  "status": "queued"
}
```

Later status:

```json
{
  "jobId": "552",
  "status": "complete",
  "imageUrl": "/images/generated/552"
}
```

## Polling

The application can periodically ask:

> Is job 552 finished yet?

This is called polling.

## Streaming

Some systems send pieces of the result as they are produced.

ChatGPT displaying text gradually is an example of streaming.

The complete answer does not need to exist before the user sees the first part.

## Agent instruction

```text
When image generation starts:

1. Create a generation job.
2. Return a job ID immediately.
3. Show queued, generating, completed, and failed states.
4. Check the job status every few seconds.
5. Stop checking after completion or failure.
6. Do not allow unlimited duplicate jobs from repeated clicks.
```

---

## Pattern 5 — Keep receiving live updates

### Example: Discord typing indicator

When someone begins typing, other users see:

> Maya is typing…

It would be inefficient for every user’s browser to ask repeatedly:

> Is anyone typing now?\
> Is anyone typing now?\
> Is anyone typing now?

Instead, the application may maintain an ongoing connection.

The server can send temporary events:

```text
Maya started typing
Maya stopped typing
New message arrived
User joined channel
User left channel
```

These events may not belong in permanent storage.

Nobody needs to retrieve:

> Maya was typing for 1.8 seconds last Tuesday.

## Permanent data versus temporary events

A message should usually be stored.

A typing indicator usually should not.

A match result should be stored.

A player’s exact cursor location may be temporary.

## Agent instruction

```text
Use live updates for typing indicators and new messages.

Store messages permanently.
Do not store every typing event.
Remove the typing indicator after a short timeout if no new event arrives.
Reconnect automatically when the live connection drops.
```

---

# 41–49 minutes — The screen can lie

Put this statement on the screen:

> **The button changed. That does not prove the action succeeded.**

A user presses **Save**.

The interface immediately displays:

> Saved

But the network request fails.

Was it saved?

No.

The interface displayed success before the server confirmed it.

Students should understand the common product states.

## Loading

The request has started, but the answer has not returned.

## Success

The server confirmed that the action succeeded.

## Empty

The request succeeded, but there is nothing to display.

## Validation error

The request contained missing or unacceptable information.

## Unauthorized

The user is not signed in or cannot be identified.

## Forbidden

The user is identified but not allowed to perform the action.

## Not found

The requested item does not exist.

## Conflict

The request clashes with the current state.

Example:

> Someone else already purchased the final ticket.

## Server error

The receiving system failed while processing the request.

## Timeout

The application waited too long without receiving an answer.

## Offline

The device has no usable network connection.

## Agent-development lesson

Students should stop asking agents only for “error handling.”

That phrase is too broad.

They should name the states:

```text
For the submission feature, create these interface states:

- untouched
- submitting
- submitted successfully
- missing required fields
- connection lost
- server unavailable
- duplicate submission
- submission rejected
```

An agent performs better when the student defines the possible realities of the feature.

---

# 49–54 minutes — Repeated requests and accidental duplication

Return to the final ticket.

The student presses **Buy**.

Nothing appears to happen.

The student presses **Buy** again.

The first request was only slow. Now the server receives two purchase requests.

Should the user be charged twice?

No.

This is why some operations need a unique request identifier.

```json
{
  "ticketId": "9082",
  "requestId": "purchase-attempt-7719"
}
```

If the same request arrives again, the server can recognize:

> I have already processed purchase-attempt-7719.

It returns the existing result instead of making another purchase.

This idea is called **idempotency**, but students do not need to memorize the word.

They need the practical rule:

> Retrying the same action should not accidentally perform it twice.

This matters for:

- Purchases
- Reservations
- Submitting assignments
- Sending invitations
- Awarding points
- Creating accounts
- Posting results
- Issuing refunds

## Agent instruction

```text
Disable the Submit button while the request is running.

Also protect against duplicate submissions on the server, because disabling the button alone is not enough.
```

---

# 54–57 minutes — Latency changes the product

Latency is the delay between sending a request and receiving the useful result.

The delay may come from:

- Distance
- Weak connection
- A busy server
- Database work
- File processing
- AI computation
- Another external service

Ask students:

### Which delay feels worse?

1. A music app taking two seconds to open an artist biography
2. A game taking two seconds to react after the player presses Jump

The number is the same.

The product effect is completely different.

Architecture depends on how quickly the feature must react.

## Product techniques

### Show progress

Useful for uploads and long processing.

### Load part of the result first

Show the first items before everything is ready.

### Prefetch

Download likely-needed information before the user requests it.

A music application may prepare the next song before the current song ends.

### Cache

Keep a recent copy closer to the user instead of downloading the same information repeatedly.

### Optimistic update

Temporarily update the screen before confirmation when the risk is low.

Example:

A heart icon may turn red immediately after the user likes a post.

If the request later fails, the application changes it back.

Do not use optimistic updates carelessly for:

- Payments
- Limited inventory
- Official approvals
- Grades
- Account deletion

---

# 57–60 minutes — Turn a vague feature into a network contract

Show students this weak instruction:

```text
Build a match-result submission page for an esports tournament.
```

An agent can build a page, but it must invent the actual system behavior.

Replace it with this:

```text
Feature: Report a match result

User action:
A team captain enters the final score and presses Submit Result.

Request must include:
- match ID
- reporting team ID
- score for each team
- optional screenshot identifier
- unique submission request ID

Server must verify:
- the user is signed in
- the user is a captain of one of the teams
- the match exists
- the match has not been finalized
- the scores are valid numbers
- the same request has not already been processed

Server work:
- save the reported result
- mark it as awaiting opponent confirmation
- notify the opposing captain

Response:
- submission status
- match ID
- reported score
- next required action

Interface states:
- editing
- uploading screenshot
- submitting
- awaiting opponent confirmation
- confirmed
- disputed
- connection failed
- unauthorized

Failure behavior:
- preserve the entered scores
- do not create a second result when Retry is pressed
- allow the captain to retry after reconnecting
```

The difference is the real lesson of Week 4.

The first prompt asks the agent to invent the architecture.

The second prompt gives the agent a product contract.

---

# Class activity — Network Detective

Give each team one feature.

Do not give every team the same kind of feature.

## Feature options

### Team 1 — Reserve the last concert seat

Focus:

- Shared source of truth
- Competing users
- Duplicate clicks
- Conflict response

### Team 2 — Upload a short film

Focus:

- Large files
- Progress
- Processing
- Failure recovery

### Team 3 — Display Discord typing indicators

Focus:

- Live connection
- Temporary events
- Reconnection
- Timeouts

### Team 4 — Generate a poster with AI

Focus:

- Long-running computation
- Job status
- Polling or streaming
- Failed generations

### Team 5 — Sync a game character across devices

Focus:

- Server authority
- Authentication
- Latest saved state
- Conflicting changes

### Team 6 — Load a playlist containing 5,000 songs

Focus:

- Pagination
- Download size
- Search
- Caching

Each team completes this map:

```text
1. What exact user action starts the process?

2. What information must leave the device?

3. What information should never be trusted from the device?

4. Which remote system receives the request?

5. What must that system verify?

6. What data or computation does it use?

7. What response should return?

8. What should the interface show while waiting?

9. Can the request safely be repeated?

10. What happens if the connection disappears?

11. Does the feature need:
    - one request
    - file upload
    - background job
    - streaming
    - ongoing connection

12. Which system owns the correct version of the result?
```

---

# Instructor demonstration — Catch the hidden traffic

Use the browser’s Network panel, but make the demonstration purposeful.

Open a simple application and perform one action.

Possible demonstrations:

- Sign in
- Load more items
- Upload a small image
- Submit a form
- Ask an AI tool a question

Have students predict how many network messages the action will create.

Then show the actual traffic.

Point out only the useful parts:

- Request address
- Request type
- Information sent
- Response
- Status
- Time
- File size

Ask:

> Which request actually caused the feature to work?

Then:

> Which requests were only loading images, analytics, fonts, or other supporting information?

The goal is for students to see that one visible action may trigger many invisible conversations.

---

# Words students should be able to use with an agent

These are not vocabulary-test terms. They are useful product-development terms.

## Browser or client

The application running on the user’s device.

## Server

A remote system that receives requests and performs services.

## Network

Connected systems capable of exchanging information.

## Internet

The larger network connecting many smaller networks.

## Domain

The human-readable name connected to an internet destination.

## URL

The structured address identifying where a request should go.

## Endpoint

A specific capability exposed at a particular path.

## Request

A structured message sent to another system.

## Payload

The information carried inside the request.

## Response

The result returned by the receiving system.

## API

The agreed rules through which software systems communicate.

## Validation

Checking whether submitted information is acceptable.

## Authentication

Checking who the user is.

## Authorization

Checking what the user is allowed to do.

## Latency

The delay before a useful response arrives.

## Upload

Information moving from the user’s device to a remote system.

## Download

Information moving to the user’s device.

## Streaming

Receiving a result gradually instead of waiting for the whole result.

## Polling

Checking repeatedly to see whether work is complete.

## Pagination

Retrieving a large collection in smaller groups.

## Cache

Keeping a reusable copy to avoid retrieving the same information repeatedly.

## Source of truth

The system whose version of the information is treated as authoritative.

---

# What not to teach

Do not spend this lecture explaining:

- Packet headers
- TCP handshakes
- IP address classes
- Router configuration
- DNS record types
- Port numbers
- HTTP protocol history
- JSON punctuation rules
- Cloud load-balancer configuration

Students can build strong products without learning those details now.

They cannot build strong products without understanding:

- What message is being sent
- What the server must verify
- Where the correct information lives
- What response is expected
- How delays and failures change the feature

---

# Week 4 deliverable — Feature Communication Contract

Each student selects three important features from their own product.

For each feature, they create a one-page contract.

## Feature name

What capability is being built?

## User action

What exact action starts it?

## Request

What information must be sent?

## Receiver

Which system receives it?

## Identity and permission

Who may perform the action?

## Validation

What must the receiving system check?

## Work

What storage, computation, AI, or external service is used?

## Response

What exact information should return?

## Interface states

What does the user see during success, waiting, emptiness, and failure?

## Duplicate behavior

What happens if the same request arrives twice?

## Connection behavior

What happens when the internet becomes slow or unavailable?

## Source of truth

Which system owns the final answer?

---

# Example completed contract

## Feature

Reserve a limited seat for a school event.

## User action

The student selects a seat and presses Reserve.

## Request

Send:

- event ID
- seat ID
- student account ID through the authenticated session
- unique reservation attempt ID

## Server validation

Check:

- the student is signed in
- the event exists
- the seat exists
- the seat is still available
- the student does not already have another seat
- the reservation attempt has not already been processed

## Server work

- Temporarily lock the seat
- Create the reservation
- Mark the seat unavailable
- Store the reservation expiration time

## Response

Return:

- reservation ID
- seat number
- expiration time
- confirmation status

## Interface states

- Available
- Reserving
- Reserved
- Already taken
- Reservation expired
- Connection lost
- Server unavailable

## Duplicate behavior

Repeated requests with the same attempt ID return the same reservation rather than creating another one.

## Source of truth

The server’s seat inventory, not the seating chart currently displayed in the browser.

---

# Final mental model

```text
A button is not a feature.

A button starts a process.

The process creates a message.

The message must contain the right information.

The receiving system must verify it.

The correct system must perform the work.

The response must describe what actually happened.

The interface must handle waiting, success, conflict, and failure.
```

## Final statement

> **A web product is not several screens connected by buttons. It is several systems connected by carefully designed conversations.**

The coding agent can write the requests and responses.

The student must decide what those conversations mean.
