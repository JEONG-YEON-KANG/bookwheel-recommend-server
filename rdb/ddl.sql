-- DDL Part 1: CREATE TABLE Statements

CREATE TABLE "user_tb" (
  "idx"                SERIAL        PRIMARY KEY,
  "nickname"           VARCHAR(255)  NOT NULL DEFAULT '새로운햄스터',
  "profile_image_path" VARCHAR(255),
  "type"               VARCHAR(50),
  "age"                INTEGER,
  "created_at"         TIMESTAMP(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at"         TIMESTAMP(3)
);

CREATE TABLE "user_basic_tb" (
  "user_idx" INTEGER      PRIMARY KEY,
  "id"       VARCHAR(255) NOT NULL UNIQUE,
  "password" VARCHAR(255) NOT NULL,
  "email"    VARCHAR(255) NOT NULL
);

CREATE TABLE "user_social_tb" (
  "user_idx"     INTEGER      PRIMARY KEY,
  "provider_name" VARCHAR(50)  NOT NULL,
  "sns_id"       VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE "book_tb" (
  "idx"                SERIAL       PRIMARY KEY,
  "title"              VARCHAR(255),
  "author"             VARCHAR(255),
  "publication_year"   INTEGER,
  "description"        VARCHAR(512),
  "book_file_path"     VARCHAR(255) NOT NULL,
  "cover_image_path"   VARCHAR(255),
  "average_rating"     REAL,
  "ratings_count"      INTEGER,
  "language_code"      VARCHAR(10),
  "isbn"               VARCHAR(20)  UNIQUE,  
  "korean_title"       VARCHAR(255),
  "korean_author"      VARCHAR(255),
  "korean_cover_path"  VARCHAR(512),
  "created_at"         TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at"         TIMESTAMP(3)
);

CREATE TABLE "book_review_tb" (
  "idx"        SERIAL       PRIMARY KEY,
  "book_idx"   INTEGER      NOT NULL,
  "user_idx"   INTEGER      NOT NULL,
  "content"    VARCHAR(512),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" TIMESTAMP(3)
);

CREATE TABLE "book_rating_tb" (
  "idx"        SERIAL       PRIMARY KEY,
  "user_idx"   INTEGER      NOT NULL,
  "book_idx"   INTEGER      NOT NULL,
  "rating"     REAL         NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" TIMESTAMP(3)
);

CREATE TABLE "tag_tb" (
  "idx"      SERIAL       PRIMARY KEY,
  "tag_name" VARCHAR(50)  NOT NULL
);

CREATE TABLE "book_tag_tb" (
  "book_idx" INTEGER NOT NULL,
  "tag_idx"  INTEGER NOT NULL,
  "count"    INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY ("book_idx", "tag_idx") -- 복합 PK 설정
);

CREATE TABLE "book_highlight_tb" (
  "idx"        SERIAL       PRIMARY KEY,
  "user_idx"   INTEGER      NOT NULL,
  "book_idx"   INTEGER      NOT NULL,
  "cfi_range"  TEXT         NOT NULL,
  "color_code" VARCHAR(10)  NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" TIMESTAMP(3)
);

CREATE TABLE "book_comment_tb" (
  "idx"             SERIAL       PRIMARY KEY,
  "user_idx"        INTEGER      NOT NULL,
  "book_idx"        INTEGER      NOT NULL,
  "highlight_idx"   INTEGER      NOT NULL,
  "content"         VARCHAR(512) NOT NULL,
  "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "friend_tb" (
  "idx"              SERIAL       PRIMARY KEY,
  "request_user_idx" INTEGER      NOT NULL,
  "receive_user_idx" INTEGER      NOT NULL,
  "status"           VARCHAR(50)  NOT NULL DEFAULT 'PENDING',
  "created_at"       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at"       TIMESTAMP(3)
);

CREATE TABLE "message_tb" (
  "idx"          SERIAL       PRIMARY KEY,
  "sender_idx"   INTEGER      NOT NULL,
  "receiver_idx" INTEGER      NOT NULL,
  "content"      VARCHAR(512) NOT NULL,
  "is_read"      BOOLEAN      NOT NULL DEFAULT FALSE,
  "sent_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at"   TIMESTAMP(3)
);

CREATE TABLE "party_tb" (
  "idx"             SERIAL       PRIMARY KEY,
  "host_user_idx"   INTEGER      NOT NULL,
  "book_idx"        INTEGER      NOT NULL,
  "title"           VARCHAR(255) NOT NULL,
  "description"     VARCHAR(512) NOT NULL,
  "max_members"     INTEGER      NOT NULL,
  "current_members" INTEGER      NOT NULL,
  "status"          VARCHAR(50)  NOT NULL DEFAULT 'OPEN',
  "start_date"      TIMESTAMP(3),
  "is_private"      BOOLEAN      NOT NULL DEFAULT FALSE,
  "password"        VARCHAR(255),
  "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at"      TIMESTAMP(3)
);

CREATE TABLE "party_members_tb" (
  "party_idx" INTEGER     NOT NULL,
  "user_idx"  INTEGER     NOT NULL,
  "status"    VARCHAR(50) NOT NULL,
  PRIMARY KEY ("party_idx", "user_idx") -- 복합 PK 설정
);

CREATE TABLE "survey_question_tb" (
  "idx"     SERIAL       PRIMARY KEY,
  "content" VARCHAR(255)
);

CREATE TABLE "survey_option_tb" (
  "idx"          SERIAL       PRIMARY KEY,
  "question_idx" INTEGER      NOT NULL,
  "content"      VARCHAR(255)
);

CREATE TABLE "survey_response_tb" (
  "idx"          SERIAL      PRIMARY KEY,
  "user_idx"     INTEGER      NOT NULL,
  "option_idx"   INTEGER      NOT NULL,
  "question_idx" INTEGER      NOT NULL,
  "created_at"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at"   TIMESTAMP(3),
  UNIQUE ("user_idx", "option_idx") 
);

CREATE TABLE "to_read_tb" (
  "user_idx"  INTEGER      NOT NULL,
  "book_idx"  INTEGER      NOT NULL,
  "marked_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("user_idx", "book_idx") -- 복합 PK 설정
);

-- DDL Part 2: FOREIGN KEYS and UNIQUE INDEXES

-- 1:1 관계 FK (PK 겸 FK 역할)
ALTER TABLE "user_basic_tb" ADD CONSTRAINT "FK_user_basic_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx") ON DELETE CASCADE;
ALTER TABLE "user_social_tb" ADD CONSTRAINT "FK_user_social_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx") ON DELETE CASCADE;

-- Survey FKs
ALTER TABLE "survey_option_tb" ADD CONSTRAINT "FK_survey_option_tb_question_idx" FOREIGN KEY ("question_idx") REFERENCES "survey_question_tb" ("idx");
ALTER TABLE "survey_response_tb" ADD CONSTRAINT "FK_survey_response_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "survey_response_tb" ADD CONSTRAINT "FK_survey_response_tb_question_idx" FOREIGN KEY ("question_idx") REFERENCES "survey_question_tb" ("idx");
ALTER TABLE "survey_response_tb" ADD CONSTRAINT "FK_survey_response_tb_option_idx" FOREIGN KEY ("option_idx") REFERENCES "survey_option_tb" ("idx");

-- Friendship FKs
ALTER TABLE "friend_tb" ADD CONSTRAINT "FK_friend_tb_request_user_idx" FOREIGN KEY ("request_user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "friend_tb" ADD CONSTRAINT "FK_friend_tb_receive_user_idx" FOREIGN KEY ("receive_user_idx") REFERENCES "user_tb" ("idx");

-- Message FKs
ALTER TABLE "message_tb" ADD CONSTRAINT "FK_message_tb_sender_idx" FOREIGN KEY ("sender_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "message_tb" ADD CONSTRAINT "FK_message_tb_receiver_idx" FOREIGN KEY ("receiver_idx") REFERENCES "user_tb" ("idx");

-- Party FKs
ALTER TABLE "party_tb" ADD CONSTRAINT "FK_party_tb_host_user_idx" FOREIGN KEY ("host_user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "party_tb" ADD CONSTRAINT "FK_party_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");

-- Party Member FKs
ALTER TABLE "party_members_tb" ADD CONSTRAINT "FK_party_members_tb_party_idx" FOREIGN KEY ("party_idx") REFERENCES "party_tb" ("idx");
ALTER TABLE "party_members_tb" ADD CONSTRAINT "FK_party_members_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");

-- Book Activity FKs
ALTER TABLE "book_review_tb" ADD CONSTRAINT "FK_book_review_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "book_review_tb" ADD CONSTRAINT "FK_book_review_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");
ALTER TABLE "book_rating_tb" ADD CONSTRAINT "FK_book_rating_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "book_rating_tb" ADD CONSTRAINT "FK_book_rating_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");
ALTER TABLE "book_tag_tb" ADD CONSTRAINT "FK_book_tag_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");
ALTER TABLE "book_tag_tb" ADD CONSTRAINT "FK_book_tag_tb_tag_idx" FOREIGN KEY ("tag_idx") REFERENCES "tag_tb" ("idx");
ALTER TABLE "to_read_tb" ADD CONSTRAINT "FK_to_read_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "to_read_tb" ADD CONSTRAINT "FK_to_read_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");
ALTER TABLE "book_highlight_tb" ADD CONSTRAINT "FK_book_highlight_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");
ALTER TABLE "book_highlight_tb" ADD CONSTRAINT "FK_book_highlight_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");

-- Comment / Highlight FKs
ALTER TABLE "book_comment_tb" ADD CONSTRAINT "FK_book_comment_tb_user_idx" FOREIGN KEY ("user_idx") REFERENCES "user_tb" ("idx");
ALTER TABLE "book_comment_tb" ADD CONSTRAINT "FK_book_comment_tb_book_idx" FOREIGN KEY ("book_idx") REFERENCES "book_tb" ("idx");
ALTER TABLE "book_comment_tb" ADD CONSTRAINT "FK_book_comment_tb_highlight_idx" FOREIGN KEY ("highlight_idx") REFERENCES "book_highlight_tb" ("idx");


-- UNIQUE INDEXES
CREATE UNIQUE INDEX "IDX_book_review_tb" ON "book_review_tb" ("book_idx", "user_idx");
CREATE UNIQUE INDEX "IDX_friend_tb" ON "friend_tb" ("request_user_idx", "receive_user_idx");
CREATE UNIQUE INDEX "IDX_party_members_tb" ON "party_members_tb" ("party_idx", "user_idx");
CREATE UNIQUE INDEX "IDX_book_tag_tb" ON "book_tag_tb" ("book_idx", "tag_idx");
CREATE UNIQUE INDEX "IDX_to_read_tb" ON "to_read_tb" ("user_idx", "book_idx");