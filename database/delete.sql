DROP TABLE `musicbotdb`.`EMAIL`;
DROP TABLE `musicbotdb`.`USER_SONG`;
DROP TABLE `musicbotdb`.`MOOD_SONG`;
DROP TABLE `musicbotdb`.`USER`;
DROP TABLE `musicbotdb`.`SONG`;
DROP TABLE `musicbotdb`.`MOOD`;

DROP TRIGGER IF EXISTS `musicbotdb`.`SONG_AFTER_DELETE`;
DROP TRIGGER IF EXISTS `musicbotdb`.`MOOD_AFTER_DELETE`;
DROP TRIGGER IF EXISTS `musicbotdb`.`USER_AFTER_DELETE`;
