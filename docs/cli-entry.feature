Feature: Published Test Module command entry
  # Restates the existing README invocation contract; not a new business requirement.

  Scenario: Missing command arguments
    Given the published module CLI is available
    When it is invoked without arguments
    Then it exits with status 2 and prints the supported usage to stderr

  Scenario: Extra command arguments
    Given the published module CLI is available
    When product-test run --request is given a path and an extra argument
    Then it exits with status 2 and prints usage before reading the request

  Scenario: No framework deployment binding
    Given a readable request with no unknown JSON fields
    And no framework deployment environment is configured
    When product-test run --request is invoked with that request
    Then it exits with status 2 and reports the missing framework JAR binding
    And it does not launch the Framework
