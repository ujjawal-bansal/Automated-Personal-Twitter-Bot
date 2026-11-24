"""Private, local review of a draft or a change to an editorial preference."""
from agent.editorial import Model
from pydantic import BaseModel


class SuggestedNote(BaseModel):
    note: str


def save_note(store, decision, note):
    print('Use the same subject to replace an earlier preference.')
    subject = input('Preference subject (blank to skip): ').strip()
    if subject:
        store.set_feedback(subject, decision, note)
        print('Preference saved.')


def review(store, post):
    print(post['text'])
    for source in post.get('sources', []):
        print(source['source'], source['url'])
    choice = input('Approve, reject, edit, or skip [a/r/e/s]: ').strip().lower()
    decisions = {'a': 'approved', 'r': 'rejected', 'e': 'edited'}
    if choice not in decisions:
        return
    edited = input('Your edited version: ').strip() if choice == 'e' else ''
    reason = input('What should carry over to future drafts? Blank for this draft only: ').strip()
    if not reason:
        return
    if edited:
        try:
            suggestion = Model().ask(
                'Suggest one short reusable preference from the stated reason and the edit. '
                'Preserve its scope. Never infer a belief from a wording change. Do not copy the draft.',
                dict(original=post['text'], edited=edited, reason=reason), SuggestedNote)
            print('Suggested note:', suggestion['note'])
            reason = input('Enter to accept, or write your own note: ').strip() or suggestion['note']
        except RuntimeError:
            print('Gemini is unavailable. Using your stated reason.')
    save_note(store, decisions[choice], reason)


def preferences(store):
    for item in store.feedback():
        print(f"{item['subject']} ({item['date']}): {item['note']}")
    choice = input('Update, forget, or quit [u/f/q]: ').strip().lower()
    if choice == 'f':
        removed = store.forget_feedback(input('Subject to forget: '))
        print('Removed.' if removed else 'No matching subject.')
    elif choice == 'u':
        note = input('Current preference in your words: ').strip()
        if note:
            save_note(store, 'updated', note)
