import os
from emmaa.db import get_db
from emmaa.subscription.email_service import send_email, \
    notifications_sender_default, notifications_return_default
from emmaa.subscription.notifications import get_user_query_delta

indra_bio_ARN = os.environ.get('INDRA_BIO_ARN')


if __name__ == '__main__':
    db = get_db('primary')
    subscribed_users = db.get_subscribed_users()

    subject_line = 'You have an update to your queries on EMMAA'

    for user_email in subscribed_users:
        delta_str_msg, delta_html_msg = get_user_query_delta(db, user_email)
        # If there is a delta, send an email
        if delta_html_msg:
            res = send_email(sender=notifications_sender_default,
                             recipients=[user_email],
                             subject=subject_line,
                             body_text=delta_str_msg,
                             body_html=delta_html_msg,
                             source_arn=indra_bio_ARN,
                             return_email=notifications_return_default,
                             return_arn=indra_bio_ARN
                             )
