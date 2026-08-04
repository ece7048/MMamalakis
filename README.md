# Michail Mamalakis Personal Site

Static academic personal site for Dr. Michail Mamalakis, built from the supplied CV, teaching statement, research plan and cover letter.

## Files

- `index.html` - main GitHub Pages-ready page.
- `styles.css` - responsive styling.
- `assets/hero-biomedical-ai.png` - generated visual asset for the hero section.
- `assets/Michail_Mamalakis_CV.pdf` - downloadable CV.
- `assets/l205-teaching-highlights.mp4` - two-minute L205 teaching proof-of-concept reel.
- `assets/l205-teaching-highlights-poster.jpg` - poster image for the teaching reel.
- `tools/create_l205_highlights.sh` - FFmpeg script for generating a two-minute L205 teaching highlights reel.

## Create The L205 Highlights Video

Copy the six source files into `source-videos/` with these exact names:

- `intro.mp4`
- `catastro.mp4`
- `lecture_attrib.mp4`
- `mech1.mp4`
- `mech2.mp4`
- `end.mp4`

Then run:

```bash
bash tools/create_l205_highlights.sh
```

The script exports `assets/l205-teaching-highlights.mp4` in the requested order.

## Publish With GitHub Pages

1. Push this folder to a GitHub repository.
2. In GitHub, open the repository settings.
3. Go to Pages.
4. Set the source to the `main` branch and root folder.
5. Save and wait for GitHub Pages to publish the URL.

For a user site, name the repository `ece7048.github.io`. For a project site, any repository name works and GitHub will publish it under `/repository-name/`.
