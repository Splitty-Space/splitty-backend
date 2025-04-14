BEGIN;

ALTER TABLE activity_user
  DROP CONSTRAINT activity_user_activity_id_fkey;

ALTER TABLE activity_user
  ADD CONSTRAINT activity_user_activity_id_fkey FOREIGN KEY (activity_id)
  REFERENCES activity (id) ON DELETE CASCADE;

DELETE FROM activity WHERE performed_by_user_id = 449640303;
DELETE FROM activity_user WHERE user_id = 449640303;
DELETE FROM expense_users WHERE user_id = 449640303;
DELETE FROM feeds WHERE user_id = 449640303;
DELETE FROM friends WHERE user_id = 449640303;
DELETE FROM friends WHERE friend_id = 449640303;
DELETE FROM transactions WHERE debtor_id = 449640303;
DELETE FROM transactions WHERE borrower_id = 449640303;
DELETE FROM users WHERE id = 449640303;

COMMIT;