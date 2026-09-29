# Week 3 — How Applications Remember

## State, storage, retrieval, and where computation happens

## What this lecture must accomplish

By the end of the hour, students should be able to look at a product idea and answer:

1. What information does this product need?
2. What shape is each piece of information?
3. What must be remembered permanently?
4. What only needs to exist temporarily?
5. Which information is a file?
6. Which information is structured data?
7. How will the application find information again?
8. Which parts happen on the user’s device?
9. Which parts happen on remote computers?
10. What should they tell a coding agent to build?

The outcome should not be that students can define “cloud” or “database.”

The outcome should be that they can say:

> “Student profiles should be structured records. Uploaded PDFs should be stored as files. Saved opportunities require a relationship between students and opportunities. The AI should retrieve relevant opportunities using filters and semantic search.”

That is the beginning of actual product architecture.

---

# The central example: One Instagram post is not one thing

## 0–8 minutes

Place an Instagram or TikTok post on the screen.

Ask:

> “What information exists behind this one post?”

Let students identify pieces.

They will probably mention:

- The image or video.
- The caption.
- The username.
- The Like count.
- Comments.

Keep going until the class exposes the real system:

- The creator’s account.
- The image or video file.
- The caption.
- The time it was posted.
- The location, if included.
- The people tagged.
- The music used.
- The people who liked it.
- The comments.
- The order of the comments.
- Who is allowed to see it.
- How many times it was viewed.
- Who watched it.
- Whether it was reported.
- Why it appeared in this particular person’s feed.
- A temporary downloaded copy on the viewer’s phone.

Then reveal:

> What looks like one post on the screen may be assembled from several different kinds of storage.

Use this picture:

```text
WHAT THE USER SEES

┌──────────────────────────────────┐
│ @alex                            │
│                                  │
│       [ VIDEO PLAYING ]          │
│                                  │
│ “First day at the tournament”    │
│ 18,429 likes                     │
│ 324 comments                     │
└──────────────────────────────────┘


WHAT THE APPLICATION USES

Account record
Post record
Video file
Like relationships
Comment records
View history
Recommendation information
Privacy rules
Temporary cached copy
```

The screen combines all these pieces into one experience.

That is the first major idea:

> A screen is not the data. It is a temporary presentation assembled from data.

---

# Part 1 — Applications need different kinds of memory

## 8–23 minutes

Do not begin with database brands.

Begin with the shapes of information.

---

## Type 1: Individual values

These are single pieces of information.

Examples:

- A username.
- A score.
- A price.
- A birth year.
- Whether an account is private.
- Whether a quiz answer is correct.

```text
username = "alex27"
score = 860
is_private = true
```

These values usually belong inside a larger record.

---

## Type 2: Structured records

A record describes one identifiable thing.

Examples:

- One student.
- One project.
- One TikTok post.
- One Roblox account.
- One scholarship.
- One basketball game.
- One inventory item.

A student record might contain:

```text
Student

Name: Maya Thompson
Grade: 12
County: Tulsa
Interests: Sports, design, healthcare
Available hours per week: 4
Project status: Exploring
```

A record is like a digital profile card.

The important point is not the word “record.” The important point is:

> The application knows which information belongs to which thing.

Without structure, an application cannot reliably answer:

- Which county is Maya in?
- Which students are in Grade 12?
- Which projects are still being explored?
- Who created this post?

---

## Type 3: Collections and lists

Applications rarely store only one item.

They store collections:

- A user’s messages.
- A playlist’s songs.
- A project’s tasks.
- A student’s quiz attempts.
- A feed of posts.
- A team’s members.
- A store’s products.

Students may think a feed is stored as one permanent list.

Explain that it may instead be created when requested.

For example:

```text
A student opens the app.

The server finds possible posts.
The server removes posts the student cannot see.
The server scores the remaining posts.
The server sends the highest-ranked posts.
```

The feed displayed on the phone may be a temporary list generated through computation.

This distinction matters:

> Some lists are stored. Other lists are created from stored information.

### Stored list

A Spotify playlist has a deliberately saved order.

### Generated list

A TikTok “For You” feed is calculated from many possible videos.

---

## Type 4: Relationships

Many applications are mostly about relationships between things.

Examples:

```text
Student SAVED Opportunity
User FOLLOWS User
Person LIKED Post
Student BELONGS TO Team
Teacher REVIEWS Project
Player OWNS Item
```

The Like does not belong only to the post or only to the user.

It connects both:

```text
Alex liked Video 9184.
```

The application needs to remember:

- Which user?
- Which video?
- When?
- Possibly from which device or session?

Use Instagram as the example.

A user record does not need to contain a giant permanent list of every full post they have liked. A separate set of relationships can connect users and posts.

```text
USERS              LIKES                POSTS

Alex ───────────── Alex → Post 17 ───── Post 17
Maya ───────────── Maya → Post 17
                   Maya → Post 24 ───── Post 24
```

This is why product designers must think beyond screens.

A “Save” button creates a relationship.

A “Follow” button creates a relationship.

“Assign this task to Maya” creates a relationship.

“Add this student to a team” creates a relationship.

---

## Type 5: Files

Images, videos, PDFs, audio recordings, and large documents behave differently from profile fields.

Examples:

- A TikTok video.
- A profile image.
- A résumé PDF.
- A recorded interview.
- A school logo.
- A project presentation.
- A voice message.

A common architecture is:

```text
DATABASE RECORD

File name: project-presentation.pdf
Owner: Maya
Uploaded: October 12
Type: PDF
Storage location: files/83a9/project-presentation.pdf
Visibility: Teacher and student
```

The database remembers information about the file.

The file storage system holds the actual file.

Use the analogy:

> The database is the library catalog. File storage is the shelves containing the books.

The catalog tells the application:

- What the file is.
- Who owns it.
- Where it is.
- Who can access it.
- When it was uploaded.

It does not need to place the complete video or PDF inside the same small record.

---

## Type 6: Events and history

Some information describes what happened rather than what currently exists.

Examples:

- A student opened an opportunity.
- A user watched 80% of a video.
- A teacher changed a grade.
- A player purchased an item.
- An application crashed.
- A student submitted a project.
- An AI produced a recommendation.

This may be stored as an event:

```text
Event: Opportunity opened
Student: Maya
Opportunity: Thunder internship
Time: 3:42 PM
Source: Search results
```

Events are useful for:

- Activity history.
- Analytics.
- Recommendations.
- Auditing.
- Diagnosing problems.
- Showing previous versions.
- Proving what happened.

Explain the difference:

```text
Current state:
Maya’s project status is “Submitted.”

History:
Monday: Draft created
Wednesday: File uploaded
Friday: Project submitted
```

A product may need both.

---

## Type 7: Meaning representations

This is where AI applications become different.

Traditional systems retrieve information through exact fields:

```text
County = Tulsa
Grade = 12
Category = Sports
```

But students may search using meaning:

> “Find opportunities where I can work with sports data, even if they do not use the words sports data.”

To support this, the application may create a numerical representation of meaning, usually called an embedding.

Do not teach the mathematics yet.

Use this analogy:

> An embedding places information on a giant invisible map of meaning.

Items with similar meaning are placed closer together.

```text
“Basketball statistics project”
        near
“Analyze player performance data”

“Animal shelter volunteer shift”
        farther away
```

A vector store or vector index helps the application locate information that is semantically similar.

Clarify the limitation:

> Semantic search does not replace normal structured filtering.

A student may ask:

> “Find AI or data opportunities near Tulsa for a high school senior.”

A good system may use both:

```text
Structured filters:
County = Tulsa
Age allowed = High school
Deadline has not passed

Semantic search:
Similar in meaning to AI, analytics, or technology
```

This is a critical architecture pattern for the projects students will build:

> Filter first using facts. Rank or search using meaning.

---

# Part 2 — Information can be temporary or persistent

## 23–31 minutes

Introduce the word **state**.

State means:

> The information the application currently needs in order to know what is happening.

There are several levels of state.

---

## Temporary screen state

Examples:

- Text typed into a form but not submitted.
- Which menu is open.
- Where the user has scrolled.
- Which image is selected.
- A video currently paused at 1:14.

This often exists only in the browser or application.

If the page is refreshed, it may disappear.

Example:

> You type a long comment, accidentally refresh the page, and the comment disappears.

The comment existed on the device but had not been saved.

---

## Session state

This lasts across several actions but may eventually expire.

Examples:

- The user is currently logged in.
- Items are temporarily in a shopping cart.
- The current game match.
- A partially completed quiz.
- A temporary upload process.

The system needs to recognize that several actions belong to the same user and session.

---

## Persistent state

This must survive after:

- The browser closes.
- The device restarts.
- The user switches devices.
- Several days pass.

Examples:

- A published post.
- A submitted assignment.
- A saved project.
- A student profile.
- A grade.
- A payment.
- A team membership.

Ask students:

> “Should this disappear when the page refreshes?”

That question helps them decide whether information must be persisted.

---

## Cached information

A cache is a temporary copy of information that exists somewhere else.

Examples:

- TikTok loads the next videos before the user swipes.
- Spotify keeps recently played album images.
- A game keeps parts of the map ready.
- A browser keeps recently used website files.
- An application temporarily remembers common search results.

The purpose is usually speed.

Explain:

> A cache is not normally the official truth. It is a fast copy.

If the cache disappears, the product should usually be able to retrieve or rebuild the information.

---

# Part 3 — Storage is chosen based on retrieval

## 31–42 minutes

This is the concept most basic app lessons miss.

Students should not ask only:

> “Where will we store this?”

They must also ask:

> “How will the product need to find it again?”

Present six common retrieval patterns.

---

## 1. Exact retrieval

> “Open project 847.”

The system retrieves one item using an identifier.

Examples:

- Open one Instagram post.
- Open one student profile.
- Load one message.
- Retrieve one order.

Useful architecture concept:

> Every important thing should have a stable identity.

```text
student_id
project_id
post_id
message_id
```

Names are not reliable identifiers because:

- Two students may have the same name.
- A user can change a username.
- A project title can change.

---

## 2. Filtering

> “Show scholarships for Oklahoma seniors.”

Filters use known fields.

Examples:

```text
state = Oklahoma
grade_allowed includes 12
deadline > today
category = STEM
```

Structured information is important when the application must filter precisely.

Bad architecture:

```text
One giant paragraph describing every scholarship.
```

Better architecture:

```text
Title
Organization
State
Eligible grades
Deadline
Category
Award amount
Description
```

The more precisely information must be filtered, the more carefully it should be structured.

---

## 3. Sorting and ranking

> “Show the newest comments.”

> “Show the lowest-price products.”

> “Show the highest-scoring players.”

Sorting requires fields such as:

- Created time.
- Price.
- Score.
- Deadline.
- Distance.
- Relevance score.

Students should ask:

> “What determines which item appears first?”

That question exposes hidden product logic.

---

## 4. Relationship retrieval

> “Show the people I follow.”

> “Show projects reviewed by this teacher.”

> “Show opportunities this student saved.”

The system follows connections between records.

```text
Student → Saved opportunities
Teacher → Reviewed projects
Team → Members
Post → Comments
```

---

## 5. Text search

> “Find documents containing the phrase ‘water quality.’”

This searches words and phrases.

Useful for:

- Titles.
- Captions.
- Articles.
- Documents.
- Product descriptions.

Text search is effective when the same or similar words are present.

---

## 6. Semantic retrieval

> “Find projects about helping rural businesses operate more efficiently.”

The exact words may not exist.

Relevant items might say:

- Small-town inventory system.
- Local vendor scheduling tool.
- Agricultural equipment maintenance tracker.

Semantic retrieval finds similarity of meaning.

---

## 7. Time-based retrieval

Applications often ask:

- What happened today?
- What changed since the last login?
- What is the newest message?
- Which deadline is approaching?
- What was the previous version?

Time must therefore be stored deliberately.

Useful fields include:

```text
created_at
updated_at
submitted_at
deleted_at
deadline
```

Students do not need to memorize the field names.

They need to understand:

> If time matters to the product, the system must record time.

---

# Part 4 — Where the work happens

## 42–48 minutes

Now return to device, server, and storage—but with more precision.

Use one action:

> A student uploads a résumé and asks the application to find matching opportunities.

---

## On the Chromebook

The browser may:

- Display the upload button.
- Let the student select a file.
- Show upload progress.
- Collect interests and location.
- Display the final recommendations.
- Temporarily hold unsaved form answers.

---

## On a remote application server

The server may:

- Confirm the student is logged in.
- Check whether the file type is allowed.
- Save the file.
- Extract text from the résumé.
- Remove or protect sensitive information.
- Call an AI model.
- Search eligible opportunities.
- Rank results.
- Save the recommendation history.
- Return the final results.

---

## In a structured database

The system may store:

```text
Student profile
Location
Grade
Interests
Opportunity records
Deadlines
Eligibility rules
Saved opportunities
Recommendation history
```

---

## In file storage

The system may store:

```text
Résumé PDF
Opportunity flyers
Organization logos
Project images
Presentation files
```

---

## In a vector index

The system may store meaning representations for:

```text
Résumé text
Student interests
Opportunity descriptions
Organization missions
```

---

## In a cache

The system may temporarily store:

```text
Popular opportunities
Recently opened profiles
Common searches
Short-lived AI results
```

Show the complete architecture:

```text
┌────────────────────────────┐
│ CHROMEBOOK / BROWSER       │
│                            │
│ Form                       │
│ File selector              │
│ Search interface           │
│ Results screen             │
│ Temporary screen state     │
└──────────────┬─────────────┘
               │
               │ request
               ▼
┌────────────────────────────┐
│ REMOTE APPLICATION         │
│                            │
│ Authentication             │
│ Permission checks          │
│ Business rules             │
│ File processing            │
│ Search orchestration       │
│ AI model calls             │
└───────┬────────┬───────────┘
        │        │
        │        │
        ▼        ▼
┌────────────┐  ┌──────────────┐
│ DATABASE   │  │ FILE STORAGE │
│            │  │              │
│ Profiles   │  │ PDFs         │
│ Projects   │  │ Images       │
│ Deadlines  │  │ Videos       │
│ Relations  │  │ Audio        │
└─────┬──────┘  └──────────────┘
      │
      ▼
┌────────────────────────────┐
│ SEARCH / VECTOR INDEX      │
│                            │
│ Keyword retrieval          │
│ Meaning-based retrieval    │
└────────────────────────────┘
```

The important lesson is:

> The system does not store everything in the same form merely because everything appears on the same screen.

---

# Part 5 — Architecture challenge: Dissect a product

## 48–56 minutes

Divide students into small groups.

Give each group one product:

- TikTok.
- Discord.
- Spotify.
- Roblox.
- Google Photos.
- Snapchat.
- ChatGPT.
- A school learning platform.

Ask them to fill in five categories.

```text
1. STRUCTURED RECORDS

What identifiable things exist?
Examples: users, posts, channels, songs, assignments


2. RELATIONSHIPS

What connects those things?
Examples: follows, memberships, Likes, saves, ownership


3. FILES

What large files must be stored?
Examples: images, audio, video, PDFs


4. EVENTS

What actions might the product record?
Examples: views, clicks, submissions, edits


5. RETRIEVAL

How does the product find or select information?
Examples: exact lookup, filters, newest first, keyword search,
semantic search, recommendation ranking
```

### Example answer: Discord

#### Structured records

- Users.
- Servers.
- Channels.
- Messages.
- Roles.

#### Relationships

- User belongs to server.
- User has role.
- Channel belongs to server.
- Message belongs to channel.
- User reacted to message.

#### Files

- Profile images.
- Uploaded images.
- Videos.
- Documents.
- Voice recordings.

#### Events

- Message sent.
- Message edited.
- User joined.
- User left.
- Reaction added.
- Moderation action performed.

#### Retrieval

- Load messages in time order.
- Search messages by word.
- Show members of a server.
- Show channels the user can access.
- Retrieve messages created after the last visit.

---

# Part 6 — The agentic coding connection

## 56–60 minutes

Explain why this matters when using coding agents.

An agent can generate code quickly.

It cannot make good product decisions if the student gives it vague instructions.

---

## Weak request

```text
Build an app for students to find opportunities.
Use a database.
```

The agent must guess:

- What a student record contains.
- What an opportunity record contains.
- How uploaded files are stored.
- Whether students can save opportunities.
- How recommendations are found.
- Whether search is exact or semantic.
- Whether recommendation history is saved.
- Who is allowed to access each profile.

The code may run while the architecture remains wrong.

---

## Strong architecture request

```text
Build an opportunity-matching application.

Store students as structured records with grade, county, interests,
availability, skills, and project preferences.

Store opportunities as structured records with organization, title,
location, age requirements, deadline, category, time commitment,
contact information, and description.

Students can save multiple opportunities, and each opportunity can be
saved by multiple students. Represent this as a relationship rather
than copying the complete opportunity into each student record.

Store uploaded résumés and organization flyers in file storage. Keep
the file owner, file type, upload date, permissions, and storage
location in the database.

Support exact filters for location, eligibility, deadline, and time
commitment.

Support semantic matching between student interests and opportunity
descriptions.

Run AI calls and permission checks on the server, not in the browser.

Save recommendation results so teachers can review what the system
suggested and why.
```

Students do not need to know how to implement all of that manually.

But they must understand enough to ask for it, inspect it, and notice when it is missing.

---

# The architecture canvas students should use

Every student project should eventually complete this sheet.

## 1. Things

What identifiable things exist?

```text
Users
Projects
Organizations
Messages
Tasks
Submissions
Opportunities
```

## 2. Fields

What facts describe each thing?

```text
Project:
Title
Owner
Status
Created date
Description
Category
```

## 3. Relationships

What connects the things?

```text
Student owns project
Teacher reviews project
Student saves opportunity
Organization publishes opportunity
```

## 4. Files

What cannot be represented as simple fields?

```text
PDFs
Images
Videos
Audio
Spreadsheets
```

## 5. Events

What actions should be remembered?

```text
Submitted
Viewed
Edited
Approved
Rejected
Downloaded
Recommended
```

## 6. Retrieval

How will users find information?

```text
By exact identity
By filters
By relationship
By time
By keyword
By meaning
By recommendation score
```

## 7. Lifetime

How long should the information exist?

```text
Only while the page is open
Until the user logs out
Until the project is completed
For the entire school year
Permanently
Until the user deletes it
```

## 8. Access

Who can see or modify it?

```text
Only the student
Student and teacher
Entire team
Public
Administrator only
```

## 9. Computation

What must the system do with it?

```text
Validate
Calculate
Rank
Summarize
Match
Notify
Generate
Translate
Moderate
```

## 10. Location

Where should each job happen?

```text
Browser
Remote application
Database
File storage
Search index
AI service
Cache
```

---

# Mistakes students should learn to recognize

## Mistake 1: Treating every piece of information as text

A profile, deadline, price, location, and eligibility rule should not be buried inside one long paragraph if the application needs to filter them.

---

## Mistake 2: Treating a file like a normal field

A video is not equivalent to a username or deadline.

Store the file separately and store information about it in the database.

---

## Mistake 3: Copying information instead of creating relationships

If 100 students save one opportunity, the system should not create 100 disconnected copies of the complete opportunity.

It should connect those students to the same opportunity.

---

## Mistake 4: Assuming AI remembers

An AI model does not automatically remember a student, prior recommendation, or project history.

The application must retrieve saved context and send the necessary information to the model.

---

## Mistake 5: Using semantic search for exact rules

Semantic similarity should not decide whether:

- A student is old enough.
- A deadline has passed.
- A county matches.
- A student has permission.
- A payment succeeded.

Exact facts and rules should be handled as structured logic.

---

## Mistake 6: Putting secrets in the browser

API keys, administrative permissions, and sensitive business rules should normally remain on the remote server.

Anything sent to the browser should be treated as potentially visible to the user.

---

## Mistake 7: Not deciding what happens after refresh

Students should ask:

> “If I close the tab and return tomorrow, should this still exist?”

If yes, it must be saved persistently.

---

# Exit ticket

Give students this product request:

> Build an application where students upload a project proposal, receive AI feedback, revise it, and submit the final version to a teacher.

Ask them to identify:

```text
Three structured records:
________________________________
________________________________
________________________________

Two relationships:
________________________________
________________________________

Two types of files:
________________________________
________________________________

Three events worth recording:
________________________________
________________________________
________________________________

One exact retrieval:
________________________________

One semantic retrieval:
________________________________

One piece of temporary browser state:
________________________________

One server-side computation:
________________________________
```

A strong answer could include:

```text
Structured records:
Student
Project
Feedback response

Relationships:
Student owns project
Teacher reviews project

Files:
Proposal PDF
Demo video

Events:
Draft created
AI feedback generated
Final version submitted

Exact retrieval:
Load all projects submitted by one student

Semantic retrieval:
Find previous projects similar to this proposal

Temporary browser state:
Unsaved edits in the proposal form

Server-side computation:
Send the proposal to an AI model and save the response
```

---

# Final message to students

> You do not need to memorize database technology.

> You need to learn to see information clearly.

Before asking an agent to build an application, identify:

- The things.
- Their fields.
- Their relationships.
- Their files.
- Their history.
- How they will be retrieved.
- Who can access them.
- What must survive after the browser closes.

Once those decisions are clear, coding agents become dramatically more useful.

Without those decisions, the agent is only guessing.
