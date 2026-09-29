# Week 5 — Frontend: Designing What the User Can See, Do, and Break

## Central idea

The frontend is not the application.

It is the **control surface** through which a person interacts with the rest of the application.

A beautiful frontend connected to nothing is a demo.

A powerful backend with a confusing frontend is a product nobody can use.

The goal this week is not to teach students how to write HTML or CSS. The goal is to teach them how to describe a frontend precisely enough that a coding agent can build the right experience.

By the end of the class, students should be able to answer:

- What does the user see?
- What can the user do?
- What changes after each action?
- What does the screen need to remember?
- What information is temporary?
- What must be saved?
- What happens while the system is working?
- What happens when something fails?
- Why was one design chosen over another?

---

# The one-hour class

## 0–5 minutes — Cold open: “The screen is lying to you”

Open TikTok, Instagram, Spotify, Discord, or a game lobby.

Ask students:

> When you tap the heart icon, what actually happened?

Most students will initially describe the visible change:

> “The heart turned red.”

But that is only the frontend reaction.

The complete sequence might be:

```text
User taps the heart
        ↓
The frontend immediately changes the icon
        ↓
The frontend sends the action to a server
        ↓
The server checks who the user is
        ↓
The server saves the like
        ↓
The recommendation system may update
        ↓
The creator’s like count may update
        ↓
Other devices eventually receive the new count
```

Now introduce the first important distinction:

> The screen changing does not prove that anything was saved.

Put a phone into airplane mode and tap something in an application. Sometimes the screen changes even though the server has not received the action.

This is called an **optimistic update**: the frontend behaves as though the action succeeded before receiving confirmation.

That can make an application feel fast, but it creates a tradeoff:

- Immediate feedback feels better.
- Waiting for confirmation is more reliable.
- If the request fails, the frontend must undo the change or show an error.

This is the first lesson students need when guiding an agent:

> Never describe only what the screen should look like. Describe what should happen before, during, after, and if the action fails.

---

## 5–12 minutes — The frontend is a control panel

Present a frontend as a combination of four things:

```text
Information
Actions
State
Feedback
```

### 1. Information

What the user can see:

- Text
- Images
- Video
- Maps
- Charts
- Cards
- Tables
- Scores
- Statuses
- Recommendations

### 2. Actions

What the user can do:

- Click
- Type
- Search
- Select
- Swipe
- Submit
- Upload
- Drag
- Delete
- Confirm
- Cancel

### 3. State

What the screen currently remembers:

- Which tab is open
- What the user typed
- Which filters are selected
- Which item is highlighted
- Whether a menu is open
- Whether results are loading
- Whether the user is logged in
- Whether a submission succeeded
- Whether an error occurred

### 4. Feedback

How the application communicates what is happening:

- Loading spinner
- Progress bar
- “Saved” message
- Error message
- Disabled button
- Empty-state message
- Confirmation screen
- Notification
- Warning before deletion

Use a game lobby as an example.

The lobby may show:

- Players currently connected
- Selected game mode
- Ready status
- Connection quality
- Countdown timer

The lobby may allow:

- Inviting a friend
- Changing a character
- Selecting a map
- Marking yourself ready
- Leaving the lobby

The screen must remember:

- The selected character
- Whether the player is ready
- Who is currently in the lobby
- Whether the game is starting

The screen must communicate:

- “Waiting for one more player”
- “Connection lost”
- “Player joined”
- “Match starting in five seconds”

This is frontend architecture. It is not decoration.

---

## 12–20 minutes — Pages are built from reusable components

Explain components as reusable pieces with a job.

Examples:

- Navigation bar
- Search box
- Video card
- Player card
- Comment panel
- Map marker
- Filter menu
- Upload area
- Notification
- Recommendation panel

A component is not just a rectangle on the screen.

A useful component usually has:

```text
Information it receives
Information it displays
Actions it allows
State it remembers
Events it produces
```

### Example: Tournament card

A gaming tournament card might receive:

- Tournament name
- Game title
- Date
- Registration status
- Number of available spots
- Thumbnail

It displays that information and may allow the user to:

- Open the tournament
- Save it
- Register
- Share it

It may have different states:

- Registration open
- Almost full
- Full
- Registration closed
- User already registered

That same card can be reused across:

- Search results
- Recommended tournaments
- Saved tournaments
- Upcoming tournaments

### Important warning: not everything should become a component

Coding agents often overcomplicate projects by turning every title, icon, and line into a separate component.

Teach students to ask:

> Will this piece appear more than once, behave independently, or need to change separately?

If yes, it may deserve to be a component.

If no, making it a separate component may add complexity without helping.

### Agent instruction

Instead of saying:

> Build the tournament page.

Say:

> Propose a component structure for this page. Explain which parts should be reusable, which parts should stay inside the page, and where creating separate components would add unnecessary complexity.

This forces the agent to reason before building.

---

## 20–28 minutes — Every screen is a collection of states

Show a music search screen.

Students may imagine only the successful version:

```text
Search box
Song results
Album covers
Play buttons
```

But the real screen has many possible states:

### Initial state

The user has not searched yet.

Possible message:

> Search for a song, artist, or album.

### Typing state

The user is entering text.

Possible behavior:

- Show suggestions
- Do nothing until they submit
- Search automatically after a short pause

### Loading state

The request has been sent, but results have not returned.

Possible behavior:

- Show a spinner
- Show loading placeholders
- Keep the previous results visible

### Success state

Results have been returned.

### Empty state

The search worked, but nothing matched.

Possible message:

> No results found. Check the spelling or try a different search.

### Error state

The search could not be completed.

Possible message:

> We could not load the results. Try again.

### Offline state

The user has lost their connection.

### Partial state

Songs loaded, but album images did not.

This leads to a critical rule:

> Designing only the successful screen means designing only a fraction of the product.

### State checklist for every important screen

Students should ask:

1. What does the screen show before the user does anything?
2. What happens while the system is working?
3. What appears when the action succeeds?
4. What appears when there is no data?
5. What appears when something fails?
6. Can the user recover without restarting?

### Agent instruction

> For this screen, identify the initial, loading, success, empty, error, and offline states. Describe what the user sees and what action they can take in each state before writing code.

---

## 28–36 minutes — Temporary information versus saved information

This is one of the most important concepts in the entire course.

A student types a long event description into a form.

The text is visible.

That does not necessarily mean it has been saved.

The information may exist only inside the browser’s current memory.

If the student:

- Refreshes the page
- Closes the tab
- Loses power
- Switches devices
- Experiences a browser crash

The text may disappear.

Teach four practical levels of frontend information.

## Level 1: Temporary screen state

Examples:

- An open menu
- The current tab
- Text typed into an unsaved form
- A selected filter

Usually disappears after refreshing.

## Level 2: Browser-saved information

Examples:

- Draft saved in the browser
- Theme preference
- Recently viewed items

May survive refreshing but may not appear on another device.

## Level 3: URL state

Examples:

```text
/events?city=Tulsa&category=music
```

The filters are stored in the address.

Benefits:

- The page can be bookmarked.
- The link can be shared.
- Refreshing keeps the same view.

## Level 4: Server-saved information

Examples:

- Account profile
- Uploaded project
- Submitted application
- Saved tournament registration
- Published event

This can usually be accessed from another device after signing in.

### The dangerous sentence

> “The user fills out the form.”

That statement is incomplete.

Students must specify:

- Is the information saved only when the user presses Submit?
- Is it automatically saved as a draft?
- How often does auto-save happen?
- Does the user see a Saved indicator?
- What happens if saving fails?
- Can the user continue on another device?
- Can the user return later?

### Tradeoff: manual save versus auto-save

#### Manual save

Advantages:

- Simpler to build
- Clear moment of submission
- Fewer server requests

Risks:

- Users forget to save
- Work may be lost
- Long forms become frustrating

#### Auto-save

Advantages:

- Reduces lost work
- Feels modern
- Supports long or multi-step tasks

Risks:

- More complicated
- The user may not know what was saved
- Frequent saving may create conflicts
- Errors must be handled carefully

### Better agent instruction

> Compare three approaches for preserving a long form: submit-only, save-draft button, and automatic saving. Evaluate them based on implementation complexity, risk of lost work, user clarity, unreliable internet, and whether students may switch devices. Recommend one and explain why.

---

## 36–43 minutes — Frontend tradeoffs: there is rarely one correct screen

Give students a challenge:

> You are building an application where students discover nearby events, clubs, volunteer opportunities, and competitions. How should the results appear?

Possible answers:

### Cards

Good for:

- Images
- Short descriptions
- Browsing
- Mobile screens

Weaknesses:

- Fewer results fit on the screen
- Comparing many options is harder

### Table

Good for:

- Comparing dates, prices, locations, or requirements
- Seeing many results quickly

Weaknesses:

- Can feel crowded
- Usually weaker on small screens
- Less visually engaging

### Map

Good for:

- Distance
- Neighborhood patterns
- Nearby opportunities

Weaknesses:

- Poor for detailed comparison
- Requires location data
- Can be difficult on weak devices
- Accessibility may be harder

### Mixed view

A map beside a list.

Good for:

- Combining location and details

Weaknesses:

- More complex
- Limited screen space
- Harder to make work well on Chromebooks and phones

The lesson is not that one is correct.

The lesson is:

> The right interface depends on what the user is trying to decide.

### Questions students should ask

- Is the user browsing or comparing?
- Is location important?
- Will they use a phone, Chromebook, or both?
- How many results will appear?
- Which details matter most?
- Does the interface still work with slow internet?
- What is the simplest version that solves the problem?

### Agent instruction

> Propose three interface options for displaying these results. For each option, explain its strengths, weaknesses, mobile behavior, development complexity, and the type of user decision it supports. Do not build anything until the options have been compared.

This teaches students to use an agent as a design partner rather than a code vending machine.

---

## 43–49 minutes — Events: every action needs a consequence

Explain an event as something the user does or something the system detects.

Examples:

```text
User clicks Register
User types a search term
User uploads an image
User changes a filter
User reaches the bottom of the page
Internet connection is lost
Results finish loading
Saving fails
```

For each event, students should map the consequences.

### Example: Upload profile image

```text
User chooses an image
        ↓
Frontend checks the file type
        ↓
Frontend checks the file size
        ↓
Frontend shows a preview
        ↓
User confirms
        ↓
Frontend begins the upload
        ↓
Progress is displayed
        ↓
Backend stores the image
        ↓
Frontend displays the saved image
```

Possible failures:

- File is too large
- Wrong file type
- Internet disconnects
- Upload takes too long
- Server rejects the file
- User closes the page

A weak agent prompt says:

> Add profile image upload.

A strong agent prompt says:

> Add profile image upload. Accept JPG, PNG, and WebP files up to 5 MB. Show a preview before uploading, display upload progress, prevent duplicate submissions, explain errors in plain language, and keep the existing profile image if the upload fails.

### The button test

For every button, students must be able to complete this sentence:

> When the user presses this button, the frontend should \_\_\_\_\_\_, the backend should \_\_\_\_\_\_, and the user should see \_\_\_\_\_\_.

Example:

> When the user presses Register, the frontend should disable the button and show progress, the backend should verify that spaces remain and save the registration, and the user should see either a confirmation or a useful error.

If students cannot complete that sentence, the button has not been designed.

---

## 49–55 minutes — The agent challenge: vague request versus architected request

Show the class this prompt:

> Build me a modern page for finding local activities.

Ask what is missing.

The answer is almost everything:

- Who is using it?
- What information is shown?
- What actions are possible?
- What devices must it support?
- What happens before results load?
- What happens when there are no results?
- What filters exist?
- What is temporary?
- What is saved?
- Which data comes from the backend?
- What does “modern” mean?
- What should be prioritized?

Now replace it with a stronger prompt.

### Strong frontend build prompt

> Design a mobile-friendly discovery page for high school students looking for local events, clubs, competitions, and volunteer opportunities.
>
> The page should include:
>
> - A keyword search
> - Category filters
> - Distance filter
> - Date filter
> - A results list
> - A save button on each result
> - A details view
>
> Before writing code:
>
> 1. Propose three layout options.
> 2. Compare cards, a table, a map, and a mixed layout.
> 3. Recommend the simplest option for a Chromebook-first MVP.
> 4. List the reusable components.
> 5. Identify the initial, loading, success, empty, error, and offline states.
> 6. Separate temporary frontend state from information that must be saved to the backend.
> 7. Explain what each button causes.
> 8. Identify any decisions that require backend support.
>
> Keep the first version simple. Do not add animations, advanced personalization, chat, or unnecessary dashboards unless they solve a stated user need.

Explain why this prompt is stronger:

- It defines the user.
- It defines the job.
- It asks the agent to compare choices.
- It prevents premature coding.
- It defines failure states.
- It separates frontend and backend responsibilities.
- It protects the project from unnecessary complexity.

---

## 55–60 minutes — Rapid design exercise: “Build the screen before the code”

Give each student one scenario.

Possible scenarios:

- Organizing a school gaming tournament
- Finding pickup basketball games
- Selling and exchanging used clothes
- Reporting broken equipment at school
- Discovering local music events
- Creating a study group
- Finding scholarships
- Coordinating rides to an event

Students have five minutes to sketch one important screen.

The drawing can be rough. No colors or design software are required.

They must label:

```text
What the user sees
What the user enters
What each button does
What is temporary
What must be saved
What happens while loading
What happens if it fails
```

Then they write one agent prompt asking for:

- Two or three design options
- A comparison of tradeoffs
- A recommended MVP
- The screen’s components
- The screen’s states
- The event produced by each action

---

# The frontend architecture canvas

Students should complete this before asking an agent to build an important screen.

## 1. User goal

What is the user trying to accomplish on this screen?

Bad:

> Use the event page.

Better:

> Find one event that fits the user’s location, schedule, and interests.

## 2. Information shown

What must the user know to make a decision?

Examples:

- Name
- Image
- Date
- Distance
- Price
- Eligibility
- Available spaces
- Organizer
- Deadline

## 3. Information collected

What does the user need to enter?

Examples:

- Search term
- Location
- Preferences
- File
- Contact information
- Confirmation

## 4. Available actions

What can the user do?

Examples:

- Search
- Filter
- Save
- Register
- Share
- Edit
- Delete
- Cancel

## 5. Frontend state

What must the screen remember temporarily?

Examples:

- Search text
- Selected filters
- Open panel
- Current step
- Unsaved form values

## 6. Saved information

What must survive refreshing, closing the browser, or changing devices?

Examples:

- Registration
- Profile
- Saved opportunity
- Submitted report
- Draft application

## 7. System states

What does the user see during:

- Initial state
- Loading
- Success
- No results
- Error
- Offline use

## 8. Event consequences

For every action:

```text
User action
Frontend reaction
Backend request
Success response
Failure response
```

## 9. Device constraints

Consider:

- Chromebook
- Phone
- Touchscreen
- Slow internet
- Small screen
- Keyboard navigation

## 10. Deliberate exclusions

What are we not building yet?

Examples:

- Animations
- Social feed
- Live chat
- Advanced recommendation engine
- Complex profile customization
- Multiple dashboards

Students should learn that removing unnecessary features is an architectural decision.

---

# Frontend tradeoffs students should learn to discuss

## One long form or multiple steps?

### One long form

Better when:

- The form is short
- Users need to review everything together
- Fields depend on one another

### Multi-step form

Better when:

- The form is long
- Different topics can be grouped
- Progress should feel manageable

Risks:

- Users may not know what comes next
- Back navigation becomes important
- Draft saving may be required

---

## Search automatically or require a Search button?

### Automatic search

Benefits:

- Feels fast
- Immediate feedback
- Useful for short queries

Risks:

- Sends many requests
- Results may jump while typing
- Performs poorly with slow internet

### Search button

Benefits:

- Predictable
- Easier to build
- Fewer requests
- Better for complicated filters

Risks:

- Adds an extra action
- May feel less responsive

---

## Modal window or separate page?

### Modal

Useful for:

- Quick confirmation
- Short edits
- Small amounts of information

Risks:

- Can feel cramped
- Poor for complicated tasks
- Back-button behavior can become confusing

### Separate page

Useful for:

- Detailed information
- Long forms
- Shareable URLs
- Complex workflows

Risks:

- More navigation
- The user may lose their place

---

## Infinite scroll or pages?

### Infinite scroll

Useful for:

- Casual browsing
- Images and entertainment content

Risks:

- Difficult to return to a specific location
- Harder to reach the footer
- Can encourage endless browsing
- More complex loading behavior

### Pagination

Useful for:

- Search
- Research
- Comparing structured results
- Returning to a specific result set

Risks:

- More clicking
- Can feel slower

---

## Show every option or guide the user?

Showing everything gives users control, but can overwhelm them.

Guiding the user reduces complexity, but may hide useful choices.

Students should ask:

> Does the user already understand the decision, or does the product need to help them make it?

---

# Common frontend mistakes made by coding agents

## 1. Building only the happy path

The page works only when data loads perfectly.

Ask the agent to explicitly test:

- Empty results
- Slow response
- Failed request
- Missing image
- Invalid input
- Duplicate submission
- Lost connection

## 2. Using fake data without making it obvious

A page may look complete while nothing is connected.

Ask:

> Mark every component that uses placeholder data and list what backend endpoint or saved data it will eventually require.

## 3. Making buttons that do nothing

The agent may generate attractive controls without behavior.

Ask:

> Create an action map showing what every clickable element does. Flag any element that is currently visual only.

## 4. Adding unnecessary complexity

Agents often add:

- Animations
- Dashboards
- Dark mode
- Notifications
- Chat
- Recommendation systems
- Complicated filters

Ask:

> Separate essential MVP features from optional improvements. Remove anything that does not directly support the user’s main task.

## 5. Ignoring mobile and Chromebook constraints

Ask:

> Review the interface at phone width and Chromebook width. Identify anything that becomes crowded, hidden, or difficult to tap.

## 6. Hiding errors in developer language

Bad error:

```text
Request failed: status 500
```

Better:

```text
We could not save your changes. Your information is still on this screen. Try again.
```

## 7. Losing user work

Ask:

> Identify every situation where the user could lose information. Recommend whether each one needs auto-save, draft saving, a warning, or no protection.

---

# Prompt students can reuse with a coding agent

> I need to design the frontend for the following user task:
>
> [Describe the user’s goal.]
>
> Do not write code immediately.
>
> First:
>
> 1. Identify the minimum information the user needs to see.
> 2. Identify the minimum information the user needs to enter.
> 3. Propose three interface approaches.
> 4. Compare their clarity, complexity, mobile usability, loading speed, and development effort.
> 5. Recommend the simplest approach that solves the main problem.
> 6. List the pages and reusable components.
> 7. Identify all important user events.
> 8. Describe the initial, loading, success, empty, error, and offline states.
> 9. Separate temporary frontend state, browser-saved state, URL state, and backend-saved information.
> 10. Explain what each button causes in the frontend and backend.
> 11. Identify ways the user could lose work.
> 12. List features that should be excluded from the first version.
>
> After this analysis, produce a screen-by-screen implementation plan. Clearly label any assumption you make.

---

# Frontend review prompt

After the agent creates the interface, students can use:

> Review this frontend as a skeptical product designer and software architect.
>
> Check:
>
> - Whether the main user goal is obvious
> - Whether every button has a clear consequence
> - Whether temporary and saved information are handled correctly
> - Whether user work can be lost
> - Whether loading, empty, error, and offline states exist
> - Whether placeholder data is clearly identified
> - Whether the interface works on a Chromebook and phone
> - Whether any components are unnecessarily complicated
> - Whether any features should be removed from the MVP
> - Whether error messages tell the user what to do next
>
> Rank the problems by severity. Do not rewrite the application until the review is complete.

---

# End-of-class understanding check

Students should be able to explain:

1. Why the frontend is not the entire application.
2. Why a visible change does not prove that information was saved.
3. What state means.
4. Why a screen requires loading, empty, and error states.
5. Why every button needs a defined consequence.
6. When information should remain temporary and when it must be saved.
7. Why two reasonable frontend designs can have different tradeoffs.
8. Why asking an agent to compare options is better than immediately asking it to build.
9. How components can reduce repetition without overcomplicating the application.
10. How to create a screen specification that another person or agent can actually implement.

---

# Final message for students

A frontend is not a collection of pretty rectangles.

It is a system of decisions:

```text
What the user knows
What the user can do
What the screen remembers
What the system saves
What happens next
What happens when things go wrong
```

A weak product description says:

> “Add a form and a Submit button.”

A strong product architect says:

> “Here is what the user is trying to accomplish, here is the information required, here is what the button triggers, here is what must be saved, here is what the user sees while waiting, and here is how the system helps them recover if it fails.”

That is the level of clarity students need before agentic coding becomes genuinely useful.
