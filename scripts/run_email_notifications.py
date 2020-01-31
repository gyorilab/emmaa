import os
from emmaa.answer_queries import QueryManager
from emmaa.subscription.email_service import send_email, \
    notifications_sender_default

indra_bio_ARN = os.environ.get('INDRA_BIO_ARN')


if __name__ == '__main__':
    qm = QueryManager()
    subscribed_users = qm.db.get_subscribed_users()

    subject_line = 'You have an update to your queries on EMMAA'

    for user_email in subscribed_users:
        delta_str_msg = qm.get_user_query_delta(user_email=user_email,
                                                report_format='str')
        delta_html_msg = qm.get_user_query_delta(user_email=user_email,
                                                 report_format='html')
        # If there is a delta, send an email
        if delta_html_msg:
            res = send_email(sender=notifications_sender_default,
                             recipients=[user_email],
                             subject=subject_line,
                             body_text=delta_str_msg,
                             body_html=delta_html_msg,
                             source_arn=indra_bio_ARN)
