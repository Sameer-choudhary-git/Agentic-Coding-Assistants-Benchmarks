You are working in a checkout of the faker-ruby/faker repository at commit 37a7ea2cdcea.

Resolve the GitHub issue below by changing the repository's source code. Do not modify or add tests unless
the issue explicitly asks for it; hidden tests will be run afterwards. Do not commit; leave your changes in
the working tree. Work offline: do not search the web or look up how the issue was fixed upstream. The issue
text is also saved in ISSUE.md in the repository root.

<issue>
Latest version generates invalid email addresses
## Describe the bug

When letting faker generate email addresses based on names, it now generates invalid email addresses, where older versions did not.

Example:

```ruby
# Faker 3.4.1
Faker::Internet.unique.email(name: " Msgr. Titus Harvey")
# => "harvey.msgr..titus@russel-von.example"
```

The email is invalid as two sequential dots appear.

```ruby
# Faker 3.3.1
Faker::Internet.unique.email(name: " Msgr. Titus Harvey")
# => "harvey_msgr_titus@corwin.example"
```

## To Reproduce

See code samples above

## Expected behavior

Factory should keep generating valid email addresses, as a major escape is to populate databases with valid looking data.

## Additional context

None
</issue>
