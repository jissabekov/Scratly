# Week 9 — Files, Documents, Images, and Search: How Applications Find Information

In Week 7, students learned that a database is not simply a place where an application “saves stuff.”

They learned to think about:

- what entities exist,
- how those entities relate,
- what questions the application needs to answer,
- how frequently information changes,
- and what kind of database architecture makes those queries efficient as the product grows.

Now introduce the next problem:

**Not everything your product knows fits naturally into rows and columns.**

Imagine building an application for a nonprofit that works with hundreds of community organizations.

For every organization, you might have:

```text
Organization
-------------
id
name
city
category
active_status
website
```

That works perfectly in a relational database.

But now each organization also has:

- a 40-page annual report,
- grant applications,
- photographs,
- program flyers,
- videos,
- meeting recordings,
- volunteer handbooks,
- email conversations,
- scanned PDFs,
- information from its website.

Suddenly, the problem is different.

You cannot reasonably create:

```text
annual_report_paragraph_1
annual_report_paragraph_2
annual_report_paragraph_3
...
```

inside your Organizations table.

The architectural question has changed from:

> **How should I organize facts?**

to:

> **How should I organize knowledge?**

That is what this week is about.

---

# 1. Start with the architecture they already know

Put this on the screen:

```text
                    PRODUCT INFORMATION

                ┌─────────────────────┐
                │      DATABASE       │
                │                     │
                │ Organization ID     │
                │ Name                │
                │ County              │
                │ Category            │
                │ Active = True       │
                └─────────────────────┘
```

Ask:

> Where would you put the organization's 80-page annual report?

Students may initially say, "the database."

The answer is not simply that this is wrong.

Technically, databases *can* store large binary objects.

The better question is:

> **Should they?**

This introduces an important architecture lesson:

**A system can often do something technically. That does not mean it is the best design.**

A database is optimized for certain kinds of work.

File storage is optimized for different kinds of work.

A search system is optimized for another kind of work.

Good architecture comes from giving each part of the system the job it is good at.

---

# 2. Three different things are hiding behind the word "data"

Students should leave this lecture thinking about information in three broad forms.

## Structured information

Information where the system already knows the shape.

```text
Student
-------
student_id: 7281
name: Maya
county: Tulsa
graduation_year: 2027
```

The application understands exactly what each value means.

You can easily ask:

```text
Show all students in Tulsa County.
```

or:

```text
Count active projects by county.
```

This is where databases are extremely powerful.

---

## Semi-structured information

Information has some organization, but the structure may vary.

Examples:

```json
{
  "organization": "Tulsa Youth Sports",
  "programs": [
    "basketball",
    "soccer",
    "summer camps"
  ],
  "contact": {
    "email": "..."
  }
}
```

APIs commonly send JSON like this.

Logs and system events may also look like this.

The information has structure, but it may not fit neatly into one fixed table.

This connects back to the SQL-versus-NoSQL discussion from Week 7.

---

## Unstructured information

Now consider:

```text
2026 Community Impact Report.pdf
```

Inside that PDF might be:

- paragraphs,
- tables,
- photographs,
- charts,
- statistics,
- names,
- addresses,
- program descriptions.

A computer receives the PDF as a file.

It does **not automatically understand the document the way a human does**.

This distinction matters enormously when students start asking coding agents to build AI applications.

They need to understand:

> **Having access to a file is not the same thing as understanding its contents.**

---

# 3. A modern product may use multiple storage systems at once

Now expand the Week 7 architecture.

```text
                       APPLICATION
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
          DATABASE      FILE STORAGE    SEARCH INDEX
              │             │             │
          structured      actual         structures
            facts          files         built for
                                          finding
                                       information
```

These systems are not competing with each other.

They solve different problems.

---

# 4. The database stores facts *about* the file

Suppose Maya uploads:

```text
tulsa-youth-sports-annual-report-2026.pdf
```

The actual PDF might go into file or object storage.

Something like:

```text
/files/organizations/381/reports/2026-report.pdf
```

The database might contain:

```text
Document
--------
document_id: 9127
organization_id: 381
filename: 2026-report.pdf
document_type: annual_report
uploaded_at: 2026-04-17
storage_location: /files/organizations/381/reports/2026-report.pdf
```

Now connect this directly to Week 7.

The database still provides:

- IDs,
- relationships,
- permissions,
- ownership,
- status,
- metadata.

The file system provides:

- the actual PDF,
- image,
- video,
- audio,
- or other large object.

This creates a relationship:

```text
ORGANIZATION
     │
     │ organization_id
     ▼
DOCUMENT RECORD
     │
     │ storage_location
     ▼
ACTUAL FILE
```

This is the same relational thinking students learned in Week 7.

The only difference is that one relationship now points outside the database.

---

# 5. What is "file storage"?

Explain that at small scale, a file might literally sit on a computer's disk.

But imagine Instagram.

Users upload billions of photographs and videos.

Instagram cannot treat each photograph as another normal database field.

Large systems commonly use **object storage**.

The basic mental model is:

```text
Object storage

        ID / location
             │
             ▼
    ┌──────────────────┐
    │       FILE       │
    │                  │
    │ photo.jpg        │
    │ video.mp4        │
    │ document.pdf     │
    └──────────────────┘
```

Examples of systems providing this type of storage include cloud services such as Azure Blob Storage or Amazon S3.

Students do not need to learn their APIs.

They need to understand the architecture:

> The database helps the application know **what the object is**.

> Object storage holds **the object itself**.

This is particularly important when steering a coding agent.

Instead of saying:

> "Build file uploads."

A student who understands the architecture can think:

> "When a user uploads a project proposal, save the PDF in object storage, create a document record connected to the student's project, store the filename and document type, and make sure the student can only access documents belonging to their project."

That is a fundamentally better product specification.

---

# 6. But storing information creates a second problem: finding it

Now imagine the system contains:

```text
100 organizations
500 PDFs
3,000 webpages
10,000 images
50,000 pages of text
```

A user asks:

> Which organizations provide programs for teenagers interested in basketball?

The system now has a problem.

The information may exist somewhere.

But **where?**

This introduces search as an architectural layer.

Search is not one technology.

Different questions require different ways of finding information.

---

# 7. Type 1 — Database filtering

Suppose the database contains:

```text
county = "Tulsa"
category = "Youth Sports"
active = true
```

Then the system can ask:

```sql
WHERE county = 'Tulsa'
AND category = 'Youth Sports'
AND active = true
```

Conceptually:

> Give me records whose fields match these conditions.

This is where the database architecture from Week 7 shines.

It is precise.

It is fast when indexed correctly.

It is predictable.

But it only works if somebody already created those fields.

Imagine the annual report says:

> "Our Saturday programs serve middle- and high-school students through competitive basketball leagues."

But nobody created a database field called:

```text
offers_basketball = true
```

A database filter cannot magically know that.

Now we need another kind of search.

---

# 8. Type 2 — Keyword or full-text search

Now the user searches:

```text
basketball
```

The system searches the text of documents.

It may find:

```text
basketball league
basketball tournament
basketball coaching
```

This is much closer to how Google-style search feels.

But now ask the students:

> What happens if the document says "youth athletics" instead of "basketball"?

Or:

> What if the user searches "teen sports programs" but the document says "athletic opportunities for adolescents"?

The ideas may be related even when the words are different.

This creates the next search problem.

---

# 9. Type 3 — Meaning-based search

Suppose the user searches:

> Opportunities for teenagers who enjoy sports.

A relevant document might say:

> We organize basketball leagues for students ages 14–18.

There may be almost no exact word overlap.

Yet humans immediately recognize the relationship.

Modern AI systems can represent pieces of text mathematically so that information with similar meaning can be found near each other.

Introduce the idea of an **embedding** conceptually.

Do not turn this into a mathematics lecture.

Explain it as:

> An embedding is a mathematical representation of meaning that allows a computer to compare pieces of information by similarity.

Very simplified:

```text
"basketball for teenagers"
          │
          ▼
    mathematical representation

"youth sports program"
          │
          ▼
    mathematical representation

These representations are relatively similar.
```

Now a system can search for information that is conceptually related rather than requiring exactly matching words.

This is often called:

**semantic search**

or

**vector search**.

---

# 10. SQL databases, search engines, and vector databases solve different questions

Build directly on Week 7.

```text
QUESTION

"Show active organizations in Tulsa."
            │
            ▼
     DATABASE QUERY


"Find documents containing basketball."
            │
            ▼
      TEXT SEARCH


"Find programs that might interest
a teenager who enjoys competitive sports."
            │
            ▼
     SEMANTIC SEARCH
```

The architectural lesson is not:

> Vector databases are better than SQL databases.

The lesson is:

> Different retrieval problems require different tools.

A sophisticated application may use all three.

For example:

```text
First:
Database filter
County = Tulsa
Active = true

Then:
Semantic search
Find programs related to sports

Then:
Ranking
Return the strongest matches
```

This is much more efficient than searching everything in the system.

Students should begin thinking about search as a **pipeline**, not a magic box.

---

# 11. What is an index?

Connect indexing to the query-efficiency discussion from Week 7.

Imagine a library with one million books.

Without a catalog:

```text
Question:
"Do you have a book by Andy Weir?"

Method:
Walk through every shelf.
Open every book.
Check the author.
```

That technically works.

It is also terrible architecture.

An index creates a prepared structure that makes particular kinds of lookup faster.

Databases may have indexes for fields such as:

```text
student_id
organization_id
county
email
```

Search systems build indexes over text.

Vector search systems build structures designed to find mathematically similar information.

The important principle is:

> **Fast retrieval usually requires work to be done before the search happens.**

You spend computation preparing information so queries can be answered efficiently later.

That is the architectural tradeoff.

```text
WITHOUT INDEXING

cheap to prepare
slow to search


WITH INDEXING

more work to prepare
more storage
much faster search
```

This is the same kind of scale thinking introduced in Week 7.

At 20 documents, almost anything works.

At 20 million documents, architecture matters.

---

# 12. The hidden pipeline behind "Upload a PDF and ask questions"

This should be the central reveal of the lecture.

Students will encounter agentic coding tools where they can type:

> Build an app where users upload PDFs and ask AI questions about them.

To the student, this sounds like one feature.

Architecturally, it may be an entire pipeline.

Show:

```text
USER UPLOADS PDF
        │
        ▼
FILE STORAGE
Store original PDF
        │
        ▼
DATABASE
Create document record
        │
        ▼
TEXT EXTRACTION
Read text from PDF
        │
        ▼
CHUNKING
Break large document into useful sections
        │
        ▼
EMBEDDING / INDEXING
Prepare sections for retrieval
        │
        ▼
SEARCH SYSTEM
Make information searchable
```

Later:

```text
USER ASKS QUESTION
        │
        ▼
SEARCH
Find relevant document sections
        │
        ▼
RETRIEVAL
Return the strongest passages
        │
        ▼
AI MODEL
Question + retrieved information
        │
        ▼
GENERATED ANSWER
```

Now they can finally understand what is happening when developers talk about **RAG — Retrieval-Augmented Generation**.

Keep the definition very simple:

> RAG means finding relevant information first and then giving that information to the AI so it can use it when answering.

The important part is the sequence:

```text
Find first.
Generate second.
```

---

# 13. Why can't we just give the AI every document?

This is where the architecture becomes interesting.

Imagine:

```text
20 PDFs
```

Maybe the system could send a huge amount of text to an AI.

Now imagine:

```text
2,000,000 PDFs
```

You cannot send the entire organization's knowledge base every time somebody asks:

> What are the eligibility requirements for this program?

Even when technically possible for smaller collections, sending unnecessary information creates problems:

- more computation,
- slower responses,
- higher cost,
- irrelevant context,
- greater chance the AI focuses on the wrong information.

The better architecture is:

```text
Huge information collection
            │
            ▼
      Search / retrieval
            │
            ▼
Small relevant subset
            │
            ▼
           AI
```

This teaches one of the most important ideas for students building AI products:

> **An AI model does not need to know everything. The surrounding system needs to deliver the right information at the right moment.**

That is systems architecture.

---

# 14. Chunking: why a document may need to be broken apart

Suppose the application has a 300-page report.

The user asks:

> How many students participated in the summer program?

The answer might exist on page 187.

Searching the entire document as one giant object is not ideal.

So systems commonly break documents into smaller pieces.

```text
300-page PDF
     │
     ├── Chunk 1
     ├── Chunk 2
     ├── Chunk 3
     ├── ...
     └── Chunk 400
```

Now the search system can retrieve:

```text
Chunk 217:
"During summer 2025, the program served 438 students..."
```

Instead of returning the entire 300-page document.

But chunking introduces design decisions.

Too large:

```text
Relevant answer buried inside lots of irrelevant text.
```

Too small:

```text
Important context may be separated from the answer.
```

Students do not need to optimize chunk sizes.

They need to know that **how information is prepared affects how well AI can retrieve it**.

That helps them recognize that poor AI answers may not actually be an "AI problem."

The failure could be:

```text
Bad document extraction
        ↓
Bad chunking
        ↓
Bad indexing
        ↓
Bad retrieval
        ↓
Wrong information reaches AI
        ↓
Bad answer
```

Changing the prompt at the bottom of that pipeline may accomplish nothing.

This is exactly the kind of systems thinking they need when working with coding agents.

---

# 15. Images create another information problem

Now show an Instagram-like example.

The system stores:

```text
photo_128783.jpg
```

The file itself is just the image object.

But Instagram may also know:

```text
user_id
upload_time
location
caption
hashtags
people tagged
width
height
content classification
```

These may live as structured metadata.

Now an AI-powered application might additionally analyze the image and produce information such as:

```text
Description:
"Teenagers playing basketball in an indoor gym."

Objects:
basketball
people
gym

Possible category:
sports
```

The image is still stored as an image.

But additional information about the image can become searchable.

The larger lesson:

> **Products often transform unstructured information into structured or searchable information.**

That transformation is a major part of modern AI architecture.

The same idea applies to:

```text
Audio
    ↓
Transcription
    ↓
Searchable text


Image
    ↓
Vision model
    ↓
Description / detected information


PDF
    ↓
Document parser
    ↓
Text / tables


Website
    ↓
Crawler or API
    ↓
Extracted content
```

AI can therefore sit not only at the end of the system answering questions.

It can also sit inside the data pipeline helping the system understand incoming information.

---

# 16. Search architecture should start from the questions users will ask

Connect directly back to Week 7.

In Week 7:

> Design your database based partly on the queries your product needs to perform.

The same principle applies here.

Do not start with:

> "We should use a vector database."

Start with:

> "What will users try to find?"

Consider three requirements.

### Requirement A

> Find organizations in Oklahoma County that are currently active.

Architecture:

```text
Database filtering
```

### Requirement B

> Search reports for the phrase "food insecurity."

Architecture:

```text
Full-text search
```

### Requirement C

> Find organizations working on problems related to children lacking reliable access to meals.

Architecture:

```text
Semantic search
```

### Requirement D

> Find active Oklahoma County organizations working on food-access problems and explain why they are relevant.

Architecture:

```text
Database filter
        ↓
Semantic search
        ↓
Retrieve relevant documents
        ↓
AI explanation
```

Now students are architecting a system rather than asking an agent to randomly assemble technologies.

---

# 17. Hybrid systems are normal

A strong real-world architecture may look like:

```text
                    APPLICATION
                         │
             ┌───────────┼───────────┐
             │           │           │
             ▼           ▼           ▼

           SQL        OBJECT       SEARCH /
        DATABASE      STORAGE      VECTOR INDEX

       students        PDFs        searchable
       projects        images      document chunks
       organizations   videos      embeddings
       permissions
       metadata
```

Then:

```text
                       AI
                        ▲
                        │
             receives retrieved context
```

There is no requirement that one technology contain everything.

This should reinforce the major idea from Week 7:

> Architecture is choosing specialized building blocks and deciding how they work together.

---

# 18. What students should pay attention to when steering an agent

By this point in the course, students should stop giving instructions such as:

> "Add AI document search."

They should be able to think through the problem.

### What information are we storing?

```text
Structured facts?
Documents?
Images?
Audio?
Video?
```

### Where should the original information live?

```text
Database?
Object/file storage?
```

### What metadata do we need?

```text
Who uploaded it?
What project does it belong to?
When was it uploaded?
What type of document is it?
Who is allowed to access it?
```

### How will users find it?

```text
Exact filters?
Keyword search?
Semantic search?
Combination?
```

### Does the content need processing?

```text
PDF → extract text
Audio → transcribe
Image → analyze
Document → chunk
```

### What happens when information changes?

If a user replaces a PDF:

```text
Do we delete the old search index?
Reprocess the document?
Generate new embeddings?
Keep document versions?
```

### What happens at scale?

Ask:

```text
Will we have:

50 documents?
50,000?
50 million?
```

The answer can completely change the architecture.

---

# 19. A good agentic-coding conversation

Show the difference.

### Weak instruction

> Build a website where students can upload documents and use AI to search them.

The agent now has to guess almost everything.

### Architecturally informed instruction

> Students should be able to upload PDF project documents. Store the original PDFs in object storage and keep document metadata in the relational database connected to the project ID and student ID. Extract the PDF text and index it so students can search by keyword and meaning. When answering AI questions, retrieve only relevant document sections and provide them to the model. Users should only be able to retrieve documents from projects they have permission to access.

Now the coding agent understands:

```text
Storage architecture
Database relationships
Document processing
Search requirements
AI retrieval
Permissions
```

The student has not written code.

But the student is still architecting the product.

That is exactly the capability the course should develop.

---

# 20. End with one architecture challenge

Give students this situation:

> You are building an application that helps Oklahoma students discover community projects.

The system has:

```text
2,000 organizations
10,000 program webpages
3,000 PDF reports
20,000 photographs
500 student projects
```

A student asks:

> "I live near Tulsa, love basketball and gaming, and want to help teenagers who do not have many activities after school. What organizations or projects might fit me?"

Ask the class:

**What happens between the student asking that question and the answer appearing?**

A strong answer might become:

```text
Student question
      │
      ▼
Understand location + interests
      │
      ▼
DATABASE
Filter active organizations near Tulsa
      │
      ▼
SEARCH INDEX
Search organization descriptions,
webpages, and documents for relevant programs
      │
      ▼
SEMANTIC SEARCH
Find ideas related to youth activities,
sports, gaming, mentoring, recreation
      │
      ▼
DATABASE
Retrieve organization details
      │
      ▼
AI
Compare the strongest matches
and explain why each might fit
      │
      ▼
FRONTEND
Display recommendations
```

Then ask the most important question:

> **Which parts of this system store information, which parts find information, and which parts reason about information?**

Students should be able to separate them:

```text
STORE
Database
Object storage

FIND
Database queries
Text search
Vector / semantic search

REASON
Application logic
AI model
```

That distinction is the main intellectual goal of Week 9.

---

# What they should understand by the end of Week 9

Students should leave with a much more sophisticated model than "PDFs go in file storage."

They should understand that a modern application's information architecture may contain several specialized layers:

```text
DATABASE
Structured facts and relationships

OBJECT STORAGE
Original files and large objects

PROCESSING PIPELINE
Turns raw content into useful information

SEARCH INDEX
Makes information efficiently discoverable

SEMANTIC / VECTOR SEARCH
Finds information based on meaning

RETRIEVAL
Selects the information needed right now

AI
Reasons over the retrieved information
```

Most importantly, they should understand the progression from Week 7:

```text
WEEK 7

How should the application
organize structured information?

        ↓

What entities exist?
How are they related?
What database fits?
How do queries stay efficient?


WEEK 9

What happens when the application's
knowledge no longer fits into tables?

        ↓

Where do files live?
How are they connected to structured data?
How is their content processed?
How does the system search thousands
or millions of pieces of information?
How does the right information reach AI?
```

The conceptual progression is therefore:

**Week 7: Model the information.**

**Week 9: Make all of the information findable.**

And that sets students up naturally for understanding more advanced AI systems, because they can now see that a useful AI product is rarely just:

```text
User → AI
```

It is much more often:

```text
User
  ↓
Application
  ↓
Structured data + files + search
  ↓
Retrieve the right information
  ↓
AI
  ↓
Useful answer
```

The intelligence of the product comes not only from the model.

It comes from **how the entire information system is architected around the model**.

# 16. How Instagram, TikTok, and YouTube store billions of images and videos

Now take the architecture much further.

Ask students:

> When you open TikTok, where are all those videos?

They are obviously not sitting inside one giant database.

And they are not stored the same way you keep:

```text
Downloads/
    video1.mp4
    video2.mp4
    photo.jpg
```

on your laptop.

At a very small scale, the idea is similar.

A file is still ultimately bytes stored somewhere.

But at internet scale, the architecture around those bytes is completely different.

Consider a TikTok-style platform.

A user uploads:

```text
my-video.mp4
```

The application may perform something like this:

```text
USER UPLOADS VIDEO
        │
        ▼
UPLOAD SERVICE
Receives the file
        │
        ▼
OBJECT STORAGE
Stores the original video
        │
        ▼
DATABASE
Creates a record describing the video
        │
        ▼
VIDEO PROCESSING
Creates multiple versions
        │
        ▼
CONTENT DELIVERY NETWORK
Distributes copies closer to users
        │
        ▼
OTHER USERS WATCH VIDEO
```

The original upload is only the beginning.

---

# 17. The video file and the video record are different things

Imagine Maya uploads a video.

The actual video might be stored somewhere conceptually like:

```text
videos/2026/07/728192837/original.mp4
```

But the database might contain:

```text
Video
-----
video_id: 728192837
user_id: 9127
caption: "First basketball tournament"
upload_time: 2026-07-18
visibility: public
likes: 1832
comments: 94
status: processed
```

The application does not normally search through a hard drive looking for:

```text
first-basketball-tournament-final-version2.mp4
```

Instead, everything is organized around IDs.

```text
video_id = 728192837
```

That ID connects the pieces.

```text
DATABASE
Video ID: 728192837
        │
        ├── owner
        ├── caption
        ├── likes
        ├── permissions
        └── storage location
                │
                ▼
        OBJECT STORAGE
        Actual video files
```

This is the same concept students learned with database relationships.

The relationship simply crosses between different storage systems.

---

# 18. How is object storage different from the file system on your computer?

This distinction is worth explaining carefully.

On your laptop, you usually think about files through folders.

```text
C:
└── Users
    └── Maya
        └── Videos
            └── Basketball
                └── tournament.mp4
```

This is a **file system**.

Files exist inside a hierarchy of folders and directories.

Applications can perform operations such as:

```text
open file
rename file
move file
change file
delete file
```

The operating system manages where those files physically exist on the disk.

For one computer, this works extremely well.

But now imagine TikTok trying to maintain:

```text
TikTok/
    User1/
        video1.mp4
        video2.mp4
    User2/
        video1.mp4
    User3/
        ...
```

for billions of videos across enormous numbers of computers.

The problem becomes much more complicated.

What happens when:

- one hard drive fails?
- one storage server fills up?
- a data center loses power?
- millions of users upload simultaneously?
- the company needs to add another million terabytes of storage?
- a user in Oklahoma requests a video physically stored in Virginia?
- the same video suddenly becomes viral?

Large cloud systems therefore often use **object storage**.

Instead of thinking primarily in folders, think:

```text
OBJECT ID
    │
    ▼
A large piece of data
    +
metadata
```

Conceptually:

```text
Object:
    ID: 728192837-original

Data:
    [billions of bytes making up the video]

Metadata:
    content_type: video/mp4
    size: 87 MB
    created_at: ...
```

The storage system takes responsibility for figuring out:

> Which physical machine actually holds these bytes?

The application usually does not need to know.

That abstraction is extremely important.

---

# 19. File system thinking versus object storage thinking

You can show the comparison like this.

```text
PERSONAL COMPUTER

Application
    │
    ▼
File system
    │
    ▼
Specific disk
    │
    ▼
File
```

Compare that with:

```text
LARGE INTERNET PLATFORM

Application
    │
    ▼
Object storage service
    │
    ▼
Thousands of storage machines
    │
    ├── Machine A
    ├── Machine B
    ├── Machine C
    └── ...
```

The application asks:

> Give me object 728192837.

The storage system figures out where it lives.

This allows the storage infrastructure to grow independently from the application.

Add more storage machines:

```text
100 servers
    ↓
1,000 servers
    ↓
100,000 servers
```

The application does not need to rewrite its entire architecture every time capacity increases.

This is one of the reasons abstraction is so important in software architecture.

---

# 20. Large platforms do not usually store only one version of a video

Suppose somebody uploads a 4K video.

Should TikTok send that exact 4K file to every phone?

No.

A user may be:

- on fast Wi-Fi,
- on slow cellular data,
- using a cheap phone,
- using a high-resolution tablet.

So after the upload, the platform may process the original video.

```text
ORIGINAL VIDEO

4K
2.5 GB
        │
        ▼
VIDEO PROCESSING
        │
        ├── 1080p version
        ├── 720p version
        ├── 480p version
        ├── low-bandwidth version
        └── thumbnail images
```

This process is commonly called **transcoding**.

The system converts one video into versions optimized for different situations.

Now the architecture may look like:

```text
Video ID: 728192837

        │
        ├── original.mp4
        ├── 1080p.mp4
        ├── 720p.mp4
        ├── 480p.mp4
        ├── thumbnail.jpg
        └── preview.jpg
```

One "video" in the product may therefore correspond to many stored objects.

The database knows that these objects all belong to the same logical video.

---

# 21. Videos are often streamed in pieces

Now introduce another surprising concept.

When someone watches a two-hour YouTube video, their device does not necessarily download the entire video before playback starts.

Instead, the video can be divided into smaller segments.

Conceptually:

```text
2-hour video

        ↓

Segment 1
Segment 2
Segment 3
Segment 4
...
Segment 1,200
```

The player downloads pieces as they are needed.

```text
PLAY VIDEO
    │
    ▼
Download segment 1
    │
    ▼
Start playing
    │
    ▼
Download segments 2, 3, 4
    │
    ▼
Continue playing
```

The system can even change quality while the video is playing.

```text
Fast connection

1080p segment
1080p segment
1080p segment

Connection slows down

720p segment
480p segment

Connection improves

1080p segment
```

This is **adaptive streaming**.

Now students can understand something they experience every day:

> Why does YouTube sometimes suddenly become blurry and then become sharp again?

The system is adapting which version of the next video segment it retrieves.

That is an architectural decision designed around:

- bandwidth,
- latency,
- user experience,
- infrastructure cost.

---

# 22. Why does a TikTok video start almost instantly?

Now introduce the idea of geographic distribution.

Imagine the original video is stored in a data center in Oregon.

A student in Oklahoma opens TikTok.

One possible architecture would be:

```text
Oklahoma phone
        │
        │ request crosses the internet
        ▼
Oregon data center
        │
        │ video travels back
        ▼
Oklahoma phone
```

That can work.

But now imagine millions of users doing this.

And imagine a viral video being watched 100 million times.

Sending every request back to the original storage location would be slow and expensive.

Large platforms therefore use systems called **Content Delivery Networks**, or CDNs.

The basic idea:

> Keep popular content closer to the people requesting it.

Conceptually:

```text
                   ORIGINAL STORAGE
                         │
                         ▼
                       CDN
            ┌────────────┼────────────┐
            │            │            │
            ▼            ▼            ▼
         Dallas       Chicago      Atlanta
          cache         cache        cache
            │
            ▼
      Oklahoma user
```

Now the Oklahoma user might receive the video from infrastructure in Dallas instead of from a distant central server.

The content is physically or logically closer.

This reduces:

```text
latency
network distance
load on the original server
```

---

# 23. A cache is a temporary shortcut

Students have probably heard the word cache without understanding why it exists.

Explain it simply.

Suppose one TikTok video becomes viral in Oklahoma.

Without caching:

```text
User 1 ────────► Original storage
User 2 ────────► Original storage
User 3 ────────► Original storage
User 4 ────────► Original storage
User 5 ────────► Original storage
```

Every request travels all the way back.

With caching:

```text
                    Original storage
                          │
                    first request
                          │
                          ▼
                     Dallas cache
                    /    /   \    \
                   ▼    ▼     ▼    ▼
                 User User  User  User
```

The nearby system keeps a copy.

Future users receive that copy.

This introduces a general architecture concept:

> Sometimes the fastest way to retrieve information is not to repeatedly calculate or retrieve it from the original source.

Instead, keep a temporary copy closer to where it will be needed.

Caches appear everywhere:

- browsers,
- databases,
- APIs,
- websites,
- games,
- video platforms,
- AI systems.

The tradeoff is that cached information can become outdated.

So every cache creates another architecture question:

> When should the cached copy be refreshed or removed?

---

# 24. What actually happens when you open Instagram?

Now bring all the pieces together.

A student opens Instagram.

They see:

```text
Profile picture
Username
Caption
Photo
Like count
Comment count
```

These pieces may not come from the same storage system.

Conceptually:

```text
USER OPENS APP
        │
        ▼
BACKEND
Figures out which posts to show
        │
        ▼
DATABASE
Returns:

post_id
user_id
caption
like_count
image_id
        │
        ▼
APP RECEIVES FEED DATA
        │
        ├───────────────┐
        │               │
        ▼               ▼
PROFILE DATA        IMAGE CDN
Database/cache      Retrieves image
        │               │
        └───────┬───────┘
                ▼
          SCREEN RENDERS POST
```

The feed itself might initially contain something like:

```text
Post 9182
User 72
Caption: "Great game tonight."
Image location: ...
Likes: 1,827
```

The phone then retrieves the actual image from the media delivery system.

This is why the database does not need to contain the image itself.

The database only needs enough information to identify and locate it.

---

# 25. How does TikTok retrieve the next video so quickly?

Now connect storage with computation.

TikTok is not simply asking:

> Give me any video.

There may be a recommendation system deciding:

```text
Video A
Video B
Video C
Video D
```

The system may return a list of IDs:

```text
728192837
928173625
172839102
```

Then:

```text
RECOMMENDATION SYSTEM
Chooses video IDs
        │
        ▼
DATABASE / CACHE
Gets metadata
        │
        ▼
CDN
Gets actual video content
        │
        ▼
PHONE
Plays video
```

The app may also retrieve the **next few videos before the user asks for them**.

Imagine the user is watching Video A.

The phone may already be doing:

```text
Currently playing:
Video A

Background:
Start retrieving Video B

Maybe also prepare:
Video C
```

This is called **prefetching**.

The system predicts what information will probably be needed next and retrieves it early.

That is why swiping to the next video often feels instantaneous.

This creates another architecture principle:

> Performance is sometimes improved by doing work before the user explicitly requests it.

But there is a tradeoff.

If the user closes the app, the system may have downloaded Video B unnecessarily.

So product architecture constantly balances:

```text
speed
vs.
bandwidth
vs.
storage
vs.
cost
```

---

# 26. Image-heavy platforms have similar processing pipelines

Suppose a user uploads a 20-megapixel photograph.

Instagram does not necessarily send the original enormous image every time somebody scrolls past the post.

The system may generate multiple versions.

```text
ORIGINAL PHOTO
6000 × 4000
        │
        ▼
IMAGE PROCESSING
        │
        ├── Full-size version
        ├── Feed-size version
        ├── Thumbnail
        └── Preview
```

Different parts of the application request different versions.

```text
Profile grid
    ↓
Thumbnail

Feed
    ↓
Medium-sized image

Full-screen viewer
    ↓
Larger image
```

Why send a 15 MB image when the user only needs a tiny thumbnail?

Again, architecture is about avoiding unnecessary work.

---

# 27. The feed is not the media

This distinction is subtle but extremely useful.

TikTok's feed may simply be something like:

```text
[
    video_id_1,
    video_id_2,
    video_id_3,
    video_id_4
]
```

The recommendation system decides **what should appear**.

The storage and delivery systems decide **how the actual content reaches the device**.

These are separate problems.

```text
RECOMMENDATION SYSTEM
"What should Maya see?"
        │
        ▼
Video IDs
        │
        ▼
MEDIA SYSTEM
"Where are those videos,
and how do we deliver them efficiently?"
```

This is another example of separating responsibilities.

One system does not need to do everything.

---

# 28. At scale, "one file" may exist in several places

On your laptop:

```text
video.mp4
```

may exist on one physical drive.

If that drive dies and you have no backup, the file may be gone.

A large platform cannot accept that risk.

Important content may therefore be copied across storage infrastructure.

Conceptually:

```text
Object: video_728192837

        ├── Copy A
        │   Storage system 1
        │
        ├── Copy B
        │   Storage system 2
        │
        └── Backup / replicated copy
            Another location
```

The exact implementation varies enormously between systems.

But the principle is:

> Large-scale storage systems are designed assuming machines will eventually fail.

A hard drive failing should not mean:

> "We lost 800,000 users' photos."

The architecture is designed around redundancy and recovery.

This is fundamentally different from thinking about a file sitting on one student's Chromebook.

---

# 29. Storage and delivery are separate architectural problems

This distinction is important.

### Storage asks:

> Where does the original information live safely?

### Retrieval asks:

> How do we find the correct object?

### Delivery asks:

> How do we get it to the user quickly?

### Processing asks:

> Do we need different versions of the object?

### Recommendation asks:

> Which object should the user receive?

These may be handled by entirely different systems.

Consider TikTok:

```text
                        USER SWIPES
                            │
                            ▼
                   RECOMMENDATION SYSTEM
                    chooses next video
                            │
                            ▼
                       VIDEO ID
                            │
                            ▼
                    METADATA SERVICE
                  finds video information
                            │
                            ▼
                         CDN
                   delivers video data
                            │
                            ▼
                       USER PHONE
```

Behind that simple swipe may be many independent systems.

This is exactly the kind of mental model students need before working with coding agents.

---

# 30. The same architecture appears at smaller scales

Students should not conclude:

> "I am not building TikTok, so none of this matters."

The same principles appear in much smaller applications.

Suppose a student's project allows a nonprofit to upload photographs of community events.

A basic architecture could be:

```text
USER UPLOADS PHOTO
        │
        ▼
OBJECT STORAGE
Store original photo
        │
        ▼
IMAGE PROCESSING
Create smaller thumbnail
        │
        ▼
DATABASE
Store:

photo_id
event_id
uploader_id
caption
upload_date
original_location
thumbnail_location
        │
        ▼
FRONTEND
Loads thumbnail in gallery
        │
        ▼
USER CLICKS PHOTO
        │
        ▼
Load larger version
```

This is the same fundamental pattern used by much larger systems.

The scale is different.

The architectural logic is not.

---

# 31. One screen may combine information from many places

Now return to the Lego model of software.

A TikTok screen might display:

```text
┌───────────────────────────────┐
│ @maya                         │
│                               │
│        VIDEO                  │
│                               │
│ ❤️ 82K    💬 1,291             │
│                               │
│ Great tournament tonight!     │
│ 🎵 Song name                   │
└───────────────────────────────┘
```

Behind the screen:

```text
Username
    ↓
User database

Video
    ↓
Object storage + CDN

Like count
    ↓
Database or cache

Comments
    ↓
Database

Recommendation
    ↓
Machine learning system

Song information
    ↓
Music catalog database

Captions
    ↓
Database

Content moderation
    ↓
AI / moderation systems
```

To the user, it is one screen.

Architecturally, it may be the result of many systems cooperating.

This reinforces one of the major ideas of the entire course:

> A product looks like one thing from the outside.

> Inside, it is a network of specialized components.

---

# 32. The deeper lesson: architecture is about movement, not just storage

By now students should begin asking more sophisticated questions.

Not only:

> Where is the data stored?

But:

```text
Where is it created?

Where is it stored?

How is it transformed?

How is it indexed?

How is it found?

How is it transported?

Where is it cached?

Who is allowed to access it?

What happens if one part fails?

What happens when usage grows 1,000×?
```

For a media platform, the lifecycle might look like:

```text
CREATE
User records video
        │
        ▼
UPLOAD
Video travels over network
        │
        ▼
STORE
Original saved in object storage
        │
        ▼
PROCESS
Generate resolutions and thumbnails
        │
        ▼
INDEX
Connect IDs, metadata, captions
        │
        ▼
DISTRIBUTE
Place content through CDN/cache
        │
        ▼
SELECT
Recommendation system chooses it
        │
        ▼
RETRIEVE
User device requests content
        │
        ▼
STREAM
Video arrives in segments
        │
        ▼
DISPLAY
Frontend shows it
```

This is much closer to how students should think when architecting products with coding agents.

They should stop thinking:

```text
"Where do I save the video?"
```

and start thinking:

```text
"What is the entire lifecycle of this video inside my system?"
```

That shift—from thinking about individual features to thinking about **information moving through a system**—is one of the most important architectural habits they can develop.
