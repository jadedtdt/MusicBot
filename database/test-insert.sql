-- SONG
-- DELETE FROM SONG WHERE URL = 'https://youtube.com' OR URL = 'https://youtube.com/new';
INSERT INTO SONG VALUES ('https://youtube.com', 'sample song title', 0, 100, NOW(), NOW()); -- succeed, valid entry
INSERT INTO SONG VALUES ('https://youtube.com', 'sample song title2', 0, 100, NOW(), NOW()); -- fail, duplicate key on url
INSERT INTO SONG VALUES ('https://youtube.com/new', 'sample song title', 0, 100, NOW(), NOW()); -- succeed, same title, different url
INSERT INTO SONG VALUES (null, null, 0, 100, NOW(), NOW()); -- fail, invalid entry on PK
SELECT * FROM SONG;



-- MOOD
-- DELETE FROM MOOD WHERE TAG = 'gene-happy';
INSERT INTO MOOD VALUES ('gene-happy', NOW(), NOW()); -- succeed, valid entry
INSERT INTO MOOD VALUES (null, NOW(), NOW()); -- fail, invalid entry
INSERT INTO MOOD VALUES ('gene-happy', NOW(), NOW()); -- fail, duplicate key on tag
SELECT * FROM MOOD;

-- USER
-- DELETE FROM USER WHERE ID = 181268300301336576 OR ID = 181268300301336575;
INSERT INTO USER VALUES (181268300301336576, 'Jadedtdt#1164', null, 'https://ytpl.com/jadedtdt', NOW(), NOW()); -- success, valid entry
INSERT INTO USER VALUES (181268300301336575, null, null, null, NOW(), NOW()); -- fail, name cannot be null
INSERT INTO USER VALUES (181268300301336576, 'RonJon#1164', null, 'https://ytpl.com/jadedtdt', NOW(), NOW()); -- fail, duplicate key on id
INSERT INTO USER VALUES (181268300301336575, 'Jadedtdt#1164', null, 'https://ytpl.com/jadedtdt', NOW(), NOW()); -- success, name is not UQ
SELECT * FROM USER;

INSERT INTO USER VALUES (181268300301336576, 'Jadedtdt#1164', 'tag1', 'https://ytpl.com/jadedtdt', NOW(), NOW()); -- success, valid entry
INSERT INTO MOOD VALUES ('tag1', NOW(), NOW()); -- succeed, valid entry
INSERT INTO MOOD VALUES ('tag2', NOW(), NOW()); -- succeed, valid entry
DELETE FROM MOOD WHERE TAG = 'tag1' -- should update mood to null
SELECT * FROM USER

-- MOOD_SONG
-- DELETE FROM MOOD WHERE TAG = 'tag1' OR TAG = 'tag2';
-- DELETE FROM SONG WHERE URL = 'https://song1.com' OR URL = 'https://song2.com';
-- DELETE FROM MOOD_SONG;
INSERT INTO MOOD VALUES ('tag1', NOW(), NOW()); -- succeed, valid entry
INSERT INTO MOOD VALUES ('tag2', NOW(), NOW()); -- succeed, valid entry
INSERT INTO SONG VALUES ('https://song1.com', 'sample song title1', 0, 100, NOW(), NOW()); -- succeed, valid entry
INSERT INTO SONG VALUES ('https://song2.com', 'sample song title2', 0, 100, NOW(), NOW()); -- succeed, valid entry
INSERT INTO MOOD_SONG VALUES ('tag1', 'https://song1.com', 0, NOW()); -- success, song with a tag
INSERT INTO MOOD_SONG VALUES ('tag1', 'https://song2.com', 0, NOW()); -- success, same tag with multiple songs
INSERT INTO MOOD_SONG VALUES ('tag2', 'https://song1.com', 0, NOW()); -- success, same song with multiple tags
INSERT INTO MOOD_SONG VALUES ('tag2', 'https://song2.com', 0, NOW()); -- success, new song with new playlist
INSERT INTO MOOD_SONG VALUES ('tag1', 'https://song1.com', 0, NOW()); -- fail, duplicate song in tag
SELECT * FROM MOOD_SONG

DELETE FROM MOOD WHERE TAG = 'tag1' -- should delete two rows in MOOD_SONG
SELECT * FROM MOOD_SONG

DELETE FROM SONG WHERE URL = 'https://song1.com' -- should delete three rows in MOOD_SONG
SELECT * FROM MOOD_SONG

-- EMAIL
INSERT INTO EMAIL VALUES (null, 'TEST_SUBJ', 'TEST_CONTENTS', NOW()); -- succeed, valid entry
