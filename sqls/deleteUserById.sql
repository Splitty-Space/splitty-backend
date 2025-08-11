BEGIN;

ALTER TABLE activity_user
  DROP CONSTRAINT activity_user_activity_id_fkey;

ALTER TABLE activity_user
  ADD CONSTRAINT activity_user_activity_id_fkey FOREIGN KEY (activity_id)
  REFERENCES activity (id) ON DELETE CASCADE;

DELETE FROM activity WHERE performed_by_user_id = 7013457029;
DELETE FROM activity_user WHERE user_id = 7013457029;
DELETE FROM expense_users WHERE user_id = 7013457029;
DELETE FROM feeds WHERE user_id = 7013457029;
DELETE FROM friends WHERE user_id = 7013457029;
DELETE FROM friends WHERE friend_id = 7013457029;
DELETE FROM transactions WHERE debtor_id = 7013457029;
DELETE FROM transactions WHERE borrower_id = 7013457029;
DELETE FROM users WHERE id = 7013457029;

COMMIT;