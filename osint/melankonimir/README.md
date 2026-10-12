# Melankonimir

**Category:** OSINT
**Challenge author:** `laragrr`
**Flag:** `FortID{H4ck1n9_15_7h3_Hev1357_3xerc1s3}`

## Description

A single image, [`images/handout.jpg`](./images/handout.jpg), and one gloomy
line of flavour text:

> She dwells with Beauty—Beauty that must die.

![The supplied challenge image](./images/handout.jpg)

The quote is from Keats' *Ode on Melancholy* — it sets the mood and the title
but doesn't point at the flag. The real starting point is the file itself.

## Initial analysis — read the metadata

Images carry metadata (camera, software, comments, identifiers). ExifTool on
the handout:

```bash
exiftool -a -G1 -s handout.jpg
```

Most fields describe how the abandoned-hospital image was AI-generated. The one
that matters is near the end:

```text
[XMP-dc] Identifier : Civitai image reference 144093319
```

Far too specific to be noise. [Civitai](https://civitai.com/) hosts AI models
and generated images, and `144093319` is an image ID.

## The trail — pivoting across services

OSINT here is a chain of small pivots, each service handing you the lookup for
the next:

1. **Civitai** — `https://civitai.com/images/144093319` (or the public API
   `https://civitai.com/api/v1/images?imageId=144093319`) shows the image was
   posted by user **`promptimirgenerativic`**.

2. **Tumblr** — that distinctive username also exists at
   `https://www.tumblr.com/promptimirgenerativic`, a blog called *"Lost and
   forgotten"* whose bio mentions a *"super-intelligent friend, who always has
   an answer"* (a nudge toward ChatGPT). Its five posts each include a
   UUID-shaped string, e.g.:

   ```text
   Only rust remains.
   6abee5e3-18e0-83ed-9ce4-64a126003985
   ```

3. **ChatGPT shared links** — those UUIDs are shared-conversation IDs:
   `https://chatgpt.com/share/6abee5e3-18e0-83ed-9ce4-64a126003985`. The
   conversation asks for a workout-logging app (sets, reps, weights, PRs,
   custom exercises) and the answer recommends **Hevy**:

   > Based on what you described, **Hevy** looks like the closest fit.

   `Hevy` (`https://hevy.com/`) is a real workout tracker — the point is *where
   to search next*, not the word itself.

4. **Hevy** — searching the full username fails; searching the recognisable
   part, **`Promptimir`**, finds a leetspeak account:

   ```text
   Display name: Promptimir
   Username:     pr0mpt1m1r      ->  https://hevy.com/user/pr0mpt1m1r
   ```

   Among ordinary workouts, the latest *Upper body B* session has one very
   out-of-place **custom exercise** named `Hacking` — matching the ChatGPT
   conversation's emphasis on custom exercises.

## Flag retrieval

The `Hacking` custom exercise uses an image of someone at a computer. The flag
is printed in small text along its bottom-left edge:

![The custom "Hacking" exercise image containing the flag](./images/custom.jpg)

```text
FortID{H4ck1n9_15_7h3_Hev1357_3xerc1s3}
```

De-leeted: *"Hacking is the Heviest Exercise"* — "Heviest" deliberately keeps
the spelling of **Hevy**, the service that closed the trail.

## Path summary

```text
handout.jpg
  -> EXIF/XMP identifier -> Civitai image 144093319
  -> user promptimirgenerativic
  -> same username on Tumblr ("Lost and forgotten")
  -> post UUIDs used as ChatGPT /share/ IDs
  -> workout-app conversation recommends Hevy
  -> Hevy user pr0mpt1m1r
  -> custom exercise "Hacking"
  -> flag printed in its image
```

## Key takeaways

- Always run `exiftool` first — an XMP `Identifier` pointing at a specific
  Civitai image ID is a deliberately planted breadcrumb, not metadata noise.
- A unique username is a cross-platform pivot: reuse it verbatim on other
  services (Tumblr, Hevy) and account for leetspeak variants (`pr0mpt1m1r`).
- Recognise service-specific ID shapes — a UUID next to a "smart friend" hint is
  a ChatGPT `/share/` link.
- OSINT is rarely one hard search; it's noticing a trail of small clues across
  several unrelated services and following it patiently.
