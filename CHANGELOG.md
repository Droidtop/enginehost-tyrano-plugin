# Changelog

All notable changes to this core are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0]

### Added
- TyranoScript's own core (Droidtop/tracker#868), until now played on the HTML core. A game runs on
  its own Tyrano engine in Enginehost's confined browser, with its saves in the save folder.
- Games that save to files (`configSave = file`), which could not save on the HTML core, save to the
  save folder too.
