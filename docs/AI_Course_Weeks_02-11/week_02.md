# Week 2 — Behind the Swipe: How an Application Actually Works

## The question driving the lesson

> **How does TikTok decide what to show you next?**

Not:

- What is a processor?
- What is RAM?
- What is storage?
- What is an operating system?

Students can learn those terms later, when the terms explain something they already want to understand.

This lecture begins with a system they already experience and gradually exposes the parts operating beneath the screen.

---

# The mental model students should leave with

```text
A person takes an action
            ↓
The device detects the action
            ↓
The application converts it into an event
            ↓
A request may travel to another computer
            ↓
The system reads its current state
            ↓
The computation layer applies rules, searches, scores or predicts
            ↓
The system may change and save its state
            ↓
A response returns
            ↓
The device renders the result
            ↓
The person takes another action
```

The last arrow matters.

Applications are not usually straight lines. They are **loops**.

```text
ACTION → COMPUTATION → RESULT → NEW ACTION
   ↑                                  ↓
   └────────── SYSTEM LEARNS ─────────┘
```

## Central punchline

> **Software is not a screen. Software is a loop that responds to events and changes state.**

---

# What students should understand by the end

Students should be able to explain:

1. Why a swipe, tap, pause, message, or movement becomes structured information.
2. What happens between an action and the visible response.
3. What the computation layer actually does.
4. Why the screen may not show the system’s true state.
5. Why online games need both a player’s device and a server.
6. Why a Snapchat streak is not really an emoji.
7. Why AI is one computation component inside an application, not the entire application.

---

# Important teaching decision

Do not begin with definitions.

Begin with a mystery.

Introduce vocabulary only when students need a name for something they have already observed.

The progression should be:

```text
Experience → Question → Mechanism → Name
```

Not:

```text
Definition → Definition → Definition → Quiz
```

---

# 60-minute lesson structure

| Time          | Segment                                         |
| ------------- | ----------------------------------------------- |
| 0–4 minutes   | The app and game census                         |
| 4–9 minutes   | Hook: What did TikTok actually receive?         |
| 9–18 minutes  | How one swipe travels through a system          |
| 18–31 minutes | Inside the computation layer                    |
| 31–41 minutes | Online games: your device is not the whole game |
| 41–48 minutes | Snapchat streaks: state plus rules              |
| 48–55 minutes | What happens when an AI application answers     |
| 55–59 minutes | Student reverse-engineering challenge           |
| 59–60 minutes | Final reveal and exit question                  |

No uninterrupted explanation should last more than approximately six minutes.

Every section should follow this pattern:

```text
Predict → Reveal → Challenge → Name the concept
```

---

# 0–4 minutes — The app and game census

Put this on screen before class begins:

> **Which three apps, games, or digital products did you use most this week?**

Students answer in chat.

Possible answers may include:

- TikTok
- Instagram
- Snapchat
- YouTube
- Spotify
- ChatGPT
- Discord
- Roblox
- Fortnite
- Minecraft
- Call of Duty
- Google Maps
- Amazon
- DoorDash
- A sports or fantasy application

As they answer, group the products live:

| Type          | Examples                          |
| ------------- | --------------------------------- |
| Content feeds | TikTok, Instagram, YouTube        |
| Communication | Snapchat, Discord, Messages       |
| Games         | Roblox, Fortnite, Minecraft       |
| AI            | ChatGPT, Gemini, Meta AI          |
| Transactions  | Amazon, DoorDash                  |
| Information   | Google Maps, weather applications |

Then say:

> “These look like completely different products. By the end of today, you will see that they are built from many of the same underlying pieces.”

Do not spend time debating which application is most popular. The poll establishes ownership: the lesson will analyze **their** digital environment.

---

# 4–9 minutes — Hook: What did TikTok actually receive?

## Slide 1

Show a full-screen image of a short-form video with no additional explanation.

Ask:

> “Suppose you watched this for three seconds and swiped away. What did TikTok learn?”

Let students answer.

Common answers:

- You did not like it.
- You were bored.
- You were not interested.
- It should stop showing that topic.
- You wanted something different.

Then challenge them:

> “Did your phone receive the sentence ‘I am bored’?”

No.

The system cannot directly observe boredom, enjoyment, confusion, or intention.

It observes behavior.

## Slide 2 — What the machine may see

Show a simplified event record:

```text
user_id: 48291
session_id: A77D
video_id: 73104
video_length: 24.0 seconds
watch_time: 3.2 seconds
completed: false
liked: false
shared: false
action: swipe_next
timestamp: 9:07:14 AM
```

Clearly label it:

> **Simplified classroom example—not TikTok’s actual internal record.**

Ask:

> “Where in this record does it say the student was bored?”

It does not.

The system must infer possible interest from observable actions.

## Punchline

> **Computers do not receive intentions. They receive evidence.**

Then add:

> “The difference between what a person means and what a system can observe is one of the most important problems in product design.”

This is a far more useful foundation than simply telling students that computers receive input.

---

# 9–18 minutes — How one swipe travels through a system

## Slide 3 — The visible experience

```text
Watch video → Swipe → Next video appears
```

Ask:

> “What happened in the invisible space between Swipe and Next Video?”

Build the answer one layer at a time.

---

## Step 1: The device detects a physical action

The touchscreen detects:

- Where the finger touched
- How the finger moved
- How far it moved
- How quickly it moved
- When the finger left the screen

The device does not initially know the gesture means “show me another video.”

It first detects physical measurements.

## Step 2: The application interprets the gesture

The application has instructions similar to:

```text
If the finger moves upward far enough,
treat the gesture as a request for the next video.
```

Now a physical movement has become an application event:

```text
SWIPE_NEXT
```

Introduce the first important term:

> **An event is a structured record that something happened.**

Examples:

```text
VIDEO_STARTED
VIDEO_PAUSED
VIDEO_COMPLETED
LIKE_PRESSED
COMMENT_POSTED
PLAYER_JUMPED
MESSAGE_SENT
ITEM_PURCHASED
```

## Punchline

> **To a person, it is a swipe. To the application, it is an event.**

---

## Step 3: The application updates what is happening locally

The application may immediately:

- Stop the current video
- Move it off the screen
- Display the next video that was already prepared
- Show a loading animation
- Record how long the previous video played

Some work happens on the student’s device.

Not every action requires a trip across the internet.

---

## Step 4: Information may travel to another computer

The application may send a message containing information such as:

```text
This user stopped video 73104 after 3.2 seconds.
Send additional videos for this session.
```

Introduce the next term:

> **A request is a message asking another part of the system to perform work or return information.**

Clarify:

> “The internet does not decide which video comes next. The internet carries the request to a computer that can make that decision.”

## Punchline

> **The internet is transportation, not intelligence.**

---

## Step 5: The system identifies the current situation

Before choosing another video, the system may need to know:

- Which user or session made the request
- What has already been shown
- What the user previously watched
- What happened during the current session
- Which videos are currently available
- Which content is appropriate for the user
- Which videos have already been removed or restricted

This collection of currently relevant information is called the system’s **state**.

Introduce the term:

> **State is what the system currently knows or believes to be true.**

Examples:

```text
The user is logged in.
The video is paused at 11.4 seconds.
The player has 63 health points.
The shopping cart contains four items.
The streak is 27 days old.
The order has been delivered.
```

## Punchline

> **Events are what happened. State is what is true now.**

---

## Step 6: The computation layer chooses what happens next

This is the part the earlier lesson failed to explain.

The computation layer does not merely “process information.” It performs identifiable types of work:

```text
Validate
Search
Compare
Calculate
Apply rules
Score
Rank
Predict
Select
Transform
```

For a short-form video feed, it may:

1. Find videos that could potentially be shown.
2. remove videos that are unavailable or unsuitable.
3. calculate information about the user, session, and videos.
4. estimate which videos the user may engage with.
5. apply product and safety rules.
6. order the videos.
7. select the next group to send.

TikTok publicly says that its recommendation system considers signals including user interactions, captions, sounds, hashtags, language, country, and device settings. It weights signals and ranks videos based on the estimated likelihood of interest. Completing a longer video, for example, may be treated as a stronger signal than a weaker contextual similarity.

The students do not need TikTok’s private algorithm.

They need to understand the architecture of the decision.

---

## Step 7: The response returns

The system sends information describing the selected videos.

The response might include:

```text
video_id
creator
caption
audio location
display dimensions
like count
comment count
content warnings
```

The actual video data may come from another specialized delivery system.

---

## Step 8: The application renders the result

Introduce the word **render**:

> **Rendering means turning information into something the user can see, hear, or interact with.**

The system may return:

```text
video_id: 88312
caption: "Friday night football..."
```

But the student does not want to see database fields.

The application converts those fields into:

- Video
- Text
- Buttons
- Animation
- Sound
- Creator profile image
- Like and comment counters

## Punchline

> **The server returns information. The application turns it into an experience.**

---

## Complete swipe flow

```text
Finger moves
    ↓
Device measures the gesture
    ↓
Application creates SWIPE_NEXT event
    ↓
Application records watch behavior
    ↓
Request travels to a server
    ↓
Server reads user and session state
    ↓
Computation retrieves, filters, scores and ranks videos
    ↓
Selected video information returns
    ↓
Application renders the next video
    ↓
The next user action becomes new information
```

## Main reveal

> **A feed is not simply a list of videos. It is a repeated decision.**

And:

> **The next video is a prediction generated from previous evidence.**

---

# 18–31 minutes — Inside the computation layer

Students need a clearer picture of “computation” than “the computer does instructions.”

Explain that most application computation falls into several recognizable categories.

---

## Computation type 1: Rules

A rule produces a predictable result.

```text
If the account is private,
only approved followers can view the post.
```

```text
If health reaches zero,
the player is eliminated.
```

```text
If the password is incorrect,
reject the login.
```

```text
If the user is under the required age,
do not show restricted content.
```

Punchline:

> **Rules turn product decisions into machine decisions.**

---

## Computation type 2: Search and retrieval

The system finds relevant information.

Examples:

- Find posts from accounts the user follows.
- Find nearby restaurants that are currently open.
- Find available game sessions.
- Find messages in this conversation.
- Find songs matching the search text.
- Find volunteer opportunities near a student’s ZIP code.

Punchline:

> **Retrieval asks: out of everything we have, which things might matter right now?**

---

## Computation type 3: Calculation and comparison

Examples:

- Calculate the total price of a shopping cart.
- Determine whether a player was inside the target area.
- Compare a submitted password with the stored representation.
- Count how many days a streak has continued.
- Calculate the distance between a driver and a customer.
- Determine which player has the lowest network delay.

Punchline:

> **A lot of “smart” software is careful counting, comparison, and timing.**

---

## Computation type 4: Scoring and ranking

The system assigns possible results a score and orders them.

Examples:

- Rank videos for a feed.
- Rank search results.
- Rank possible delivery drivers.
- Rank players or sessions for matchmaking.
- Rank songs for a playlist.
- Rank project recommendations for a student.

## Live classroom ranking exercise

Show this fictional user history:

```text
Completed:
• High school football highlights
• Tornado footage
• A comedy sketch

Shared:
• Oklahoma storm video

Skipped quickly:
• Makeup tutorial
• Cryptocurrency promotion

Rewatched:
• Basketball trick shot
```

Then show five possible next videos:

1. Local high school football upset
2. Makeup product review
3. Basketball buzzer-beater
4. Oklahoma storm explanation
5. Random celebrity interview

Ask students to rank them.

After they answer, ask:

> “What did you optimize?”

Possible answers:

- Probability of watching
- Probability of sharing
- Relevance to Oklahoma
- Variety
- Safety
- Newness
- Creator popularity

Then reveal the deeper issue:

> “There is no neutral ranking. Someone must decide what a high score means.”

A platform could optimize for:

```text
Long watch time
More shares
More purchases
More learning
More variety
More social connection
Less harmful content
More creator fairness
```

Different goals produce different feeds.

## Punchline

> **Ranking is a product decision converted into mathematics.**

And:

> **The computer is fast. The objective is human.**

This concept will matter later when students design their own recommendation and AI systems.

---

## Computation type 5: Model inference

A trained model takes information and produces a prediction, classification, score, or generated result.

Examples:

- Estimate whether a user will watch a video.
- Identify possible spam.
- Recognize speech.
- Estimate a player’s skill.
- Recommend a song.
- Generate text.
- Identify an object in a photograph.

Avoid saying “the AI thinks.”

Say:

> “The model calculates an output from patterns learned during training.”

Punchline:

> **AI does not replace computation. AI is one kind of computation.**

---

# 31–41 minutes — Online games: your device is not the whole game

## Opening question

> “When you press Jump in Fortnite, Roblox, or another online game, does your console send a video of your character jumping to every other player?”

No.

That would be far too slow and wasteful.

Instead, the system exchanges events and state.

---

## What happens when a player presses Jump?

```text
Player presses Jump
        ↓
Game client detects the input
        ↓
The client may immediately predict and display the jump
        ↓
A message describing the action travels to the game server
        ↓
The server checks whether the jump is valid
        ↓
The server updates the official game state
        ↓
Updated state is sent to connected players
        ↓
Each player’s device renders the result
```

Introduce two terms:

### Client

The application running on the player’s device.

### Server

The computer coordinating the shared game.

The client is responsible for things such as:

- Reading controller input
- Rendering graphics
- Playing sound
- Predicting immediate movement
- Displaying interface elements

The server is responsible for things such as:

- Maintaining the official shared state
- Determining whether actions are valid
- Updating player positions
- Applying game rules
- Coordinating the session
- Sending state changes to players

Unreal Engine documentation describes this as a server-authoritative model: the true game state exists on the server, and state changes are replicated to connected clients, which render their local versions of the world.

---

## Ask the cheating question

> “Why not let every player’s computer decide what is true?”

Show this fictional message:

```text
My health: 9,999
My ammunition: unlimited
My position: directly behind the opponent
I won the match
```

Students will immediately understand the problem.

The server acts as the referee.

## Punchline

> **Your device proposes an action. The server settles the argument.**

---

## Why movement still appears immediate

If every button press waited for a round trip to the server, the game would feel delayed.

Many games display a predicted result locally while waiting for confirmation.

Conceptually:

```text
Client: “You probably jumped, so I will show it now.”
Server: “I checked. The jump was valid.”
```

Sometimes they disagree:

```text
Client: “You reached the doorway.”
Server: “No. You were hit before you arrived.”
```

The game corrects the local state, producing lag, snapping, or rubber-banding.

## Punchline

> **A responsive game sometimes shows the prediction before it receives the truth.**

This leads directly into one of the most important ideas in application design.

---

# The screen is not necessarily the truth

Use an Instagram-style Like button.

A student presses the heart.

The heart may turn red immediately.

Ask:

> “Has the like definitely been saved?”

Not necessarily.

Many applications use **optimistic updates**:

```text
1. Show the expected result immediately.
2. Send the request to the server.
3. Wait for confirmation.
4. Keep the change if successful.
5. Reverse it if the request fails.
```

This is why an action may briefly appear successful and then disappear when the connection fails.

## Punchline

> **The screen may show what the application expects to become true—not what the server has confirmed is true.**

This is a much more meaningful way to teach temporary versus permanent information.

---

# 41–48 minutes — Snapchat streaks: state plus rules

## Opening question

Show:

```text
🔥 127
```

Ask:

> “Where does the streak actually exist?”

Possible answers:

- In Snapchat
- On the phone
- In the account
- In the fire emoji

Then say:

> “The fire emoji is not the streak. It is only the picture Snapchat renders.”

A simplified streak record could look like:

```text
relationship_id: A19-B72
last_snap_A_to_B: July 17, 8:12 AM
last_snap_B_to_A: July 17, 7:44 AM
streak_days: 127
status: active
```

The actual feature consists of:

```text
Stored information
        +
Timing rules
        +
New events
        =
Current streak state
```

Snapchat says a streak requires people to exchange qualifying photo or video Snaps each day; the displayed number represents the streak’s age, while an hourglass indicates it is close to expiring.

---

## Trace the computation

```text
Student sends a Snap
        ↓
SEND_SNAP event is created
        ↓
System verifies sender and recipient
        ↓
System determines whether it is a qualifying Snap
        ↓
Timestamp is stored
        ↓
System checks both directions and the time window
        ↓
Streak state is maintained, increased or expired
        ↓
Updated state returns
        ↓
Application renders fire, number or hourglass
```

## Punchline

> **The emoji is not the feature. The stored state and the rules are the feature.**

This is the cleanest introduction to permanent information:

- The displayed emoji can disappear from the screen.
- The stored streak record still exists.
- Another device can retrieve it.
- The system can calculate whether it is active.
- The interface renders the calculated state.

---

# 48–55 minutes — What happens when an AI application answers?

Use a prompt connected to the course:

```text
Suggest three realistic community projects for a student
in rural Oklahoma who likes basketball and video editing.
```

Ask:

> “What happened between pressing Send and seeing the answer?”

Build the chain.

---

## Step 1: The screen collects information

The application collects:

- The current message
- Some conversation context
- Account or session information
- Application instructions
- Possibly uploaded documents or images

## Step 2: The application creates a request

The request may contain much more than the one visible message.

Conceptually:

```text
User message
Conversation history
System instructions
Output format
Available tools
Safety rules
```

## Step 3: The request travels to a server

The server may:

- Verify the account
- Check permissions
- Determine which model to use
- Retrieve saved context
- Decide which tools are available
- Record usage
- Limit the size of the request

## Step 4: The AI model performs inference

At a simplified level:

1. Text is converted into smaller machine-readable units.
2. The model processes the supplied context.
3. It repeatedly calculates likely next pieces of the response.
4. The generated pieces are assembled into text.

Do not claim that the model is pulling a complete answer from a shelf.

Do not claim that it understands the student’s entire life.

It processes the context supplied to it.

## Step 5: The application may call other systems

An AI application may also:

- Search the web
- Query a database
- Read a document
- Check a calendar
- Execute code
- Call another model
- Ask a human for approval

The model is one component coordinating or participating in a larger workflow.

## Step 6: The response returns and is rendered

The application may stream the response piece by piece, format it, save it, attach citations, or display tool results.

## Complete AI flow

```text
Student enters request
        ↓
Application packages request and context
        ↓
Server verifies identity and permissions
        ↓
Relevant information may be retrieved
        ↓
AI model performs inference
        ↓
Tools or other systems may be called
        ↓
Application checks and stores results
        ↓
Response returns
        ↓
Screen renders the answer
```

## Punchlines

> **The AI does not automatically know the user. It knows the context the system provides.**

> **AI is a computation service inside a product pipeline.**

> **A powerful model inside a badly designed system still produces a bad product.**

This last statement prepares students for agentic coding. Their job will not simply be to “add AI.” Their job will be to design the complete system around it.

---

# 55–59 minutes — Reverse-engineering challenge

Divide the 8–10 students into pairs.

Each pair selects one interaction:

- Like an Instagram Reel
- Swipe to the next TikTok
- Maintain a Snapchat streak
- Join an online game
- Send a Discord message
- Ask an AI assistant a question
- Add an item to an Amazon cart
- Request a DoorDash order
- Upload a YouTube video

Give them this template:

```text
1. What action did the person take?

2. What event did the application create?

3. What information probably traveled?

4. What current state did the system need to read?

5. What computation occurred?
   • Rule?
   • Search?
   • Calculation?
   • Ranking?
   • Model prediction?

6. What information changed or was saved?

7. What response returned?

8. What did the application render?
```

Give them three minutes.

Each pair then gets 30 seconds to explain its system.

Do not correct every technical imperfection.

Correct only magical statements.

When a student says:

> “TikTok knows you like basketball.”

Ask:

> “What evidence could it actually observe?”

When a student says:

> “The game moves the player.”

Ask:

> “Which part—the client or the server?”

When a student says:

> “Snapchat saves the fire emoji.”

Ask:

> “What information would it need to save in order to calculate the emoji?”

When a student says:

> “The AI gives an answer.”

Ask:

> “What information did the application send to the model?”

This questioning style forces architectural thinking.

---

# 59–60 minutes — Final reveal

Return to the original TikTok example:

```text
Watch → Swipe → Next video
```

Replace it with:

```text
Physical gesture
      ↓
Application event
      ↓
Local interface update
      ↓
Network request
      ↓
Current state retrieved
      ↓
Candidates found
      ↓
Rules applied
      ↓
Predictions calculated
      ↓
Videos ranked
      ↓
Response returned
      ↓
Video rendered
      ↓
New behavior recorded
```

Then say:

> “Nothing magical happened. But many different things happened extremely quickly.”

## Final punchline

> **When software feels simple, it usually means someone worked hard to hide the complexity.**

And end with:

> “From now on, you are not allowed to say, ‘the app does it.’ Name the part of the system that does it.”

---

# Exit question

Put this in the chat:

> **You press Like. The heart turns red, but after several seconds it changes back. Explain what probably happened.**

A strong answer:

```text
The client updated the screen immediately because it expected
the request to succeed. It then sent the Like event to the server.
The server did not confirm the change, possibly because the network
failed or the request was rejected. The application returned the
screen to the confirmed server state.
```

This single answer demonstrates that the student understands:

- Input
- Events
- Client
- Server
- Network
- State
- Saving
- Responses
- Rendering

---

# Vocabulary introduced through the lesson

| Term            | Student-level meaning                                                                 |
| --------------- | ------------------------------------------------------------------------------------- |
| Event           | A structured record that something happened                                           |
| Client          | The application operating on the user’s device                                        |
| Server          | A computer providing data, coordination, or computation to clients                    |
| Request         | A message asking another system to perform work                                       |
| State           | What the system currently knows or believes is true                                   |
| Computation     | Rules, searches, calculations, comparisons, rankings, predictions, or transformations |
| Retrieval       | Finding information that may be relevant                                              |
| Ranking         | Ordering possible results according to calculated scores                              |
| Model inference | Using a trained model to calculate an output                                          |
| Response        | Information returned after a request                                                  |
| Render          | Turn information into a visible, audible, or interactive experience                   |
| Persistence     | Saving information so it remains available later                                      |
| Feedback loop   | Using previous actions to influence future results                                    |

Do not test students on the definitions in isolation.

Test whether they can use the terms while explaining a product.

---

# The six sentences worth repeating

Use these throughout the lecture and later weeks:

> **Computers do not receive intentions. They receive evidence.**

> **Events are what happened. State is what is true now.**

> **The internet is transportation, not intelligence.**

> **Ranking is a product decision converted into mathematics.**

> **The screen may show a prediction before the server confirms the truth.**

> **AI is one computation component inside a complete product.**

---

# Optional after-class assignment

## Assignment: Capture ten seconds of invisible software

Students choose one application they use.

They record or describe a single 5–10 second interaction, such as:

- Swiping through two videos
- Sending a Snap
- Joining a match
- Liking a post
- Searching for a song
- Asking an AI question
- Adding an item to a cart

They then create a one-page system trace:

```text
ACTION
What did I physically do?

EVENT
How might the application record it?

REQUEST
What information might travel?

STATE
What did the system need to know?

COMPUTATION
What rule, search, calculation, ranking or model was used?

STATE CHANGE
What information might be saved?

RESPONSE
What returned?

RENDERING
What did I see, hear or experience?
```

The assignment is not graded on knowing a company’s private architecture.

It is graded on whether the student can replace:

> “The app did something”

with:

> “These components probably exchanged this information and performed these types of computation.”

---

# Instructor guidance for keeping attention

## Change the mode every few minutes

Rotate between:

- Prediction
- Short explanation
- Live poll
- Diagram reveal
- Challenge question
- Pair activity
- Product comparison

## Reveal diagrams progressively

Do not show a complete 12-box architecture diagram and begin reading it.

Start with:

```text
Swipe → ?
```

Then reveal one layer whenever students identify a new question.

## Use disagreement

Good questions include:

- Is the heart on the screen the real Like?
- Does TikTok know you are bored?
- Who decides whether a player was hit?
- Does Snapchat save an emoji?
- Does ChatGPT automatically know your previous conversations?
- Is the next video selected before or after you swipe?
- Can the screen display something that has not been saved?

These questions are stronger than “What is input?”

## Treat students as experienced users

They already know what lag, feeds, streaks, recommendations, loading screens, notifications, and failed messages feel like.

Your job is to connect those experiences to architecture.

## Do not overuse analogies

Use direct system explanations first.

Only introduce an analogy when it clarifies a specific mechanism better than the mechanism itself. Do not let an analogy replace the actual architecture.
