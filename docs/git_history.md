## ⚠️ Notes on Git History Rewriting

This project has undergone a Git history rewrite to remove all `.ini` files from past commits. This is a **destructive** and **irreversible** operation.

-   If you cloned the repository before this change, you might need to **delete your local copy and re-clone** the repository.
-   If you are collaborating, ensure all team members are aware of this change and update their repositories accordingly.
-   After rewriting, you will need to **re-add your `origin` remote** (if removed by `git filter-repo`) and then perform a `git push --force` to update the remote repository.
