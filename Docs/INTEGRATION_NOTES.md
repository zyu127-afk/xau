# Integration notes

External SDKs and broker terminals are deliberately isolated behind adapters. Core logic remains testable without proprietary binaries; the actual adapters are validated against the user's installed versions during demo/paper acceptance.
