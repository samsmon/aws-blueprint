# AWS Architecture Icons

The diagram scripts in `diagrams/` draw from the official AWS Architecture Icons
asset package, so every diagram uses one known set of icons.

**The icons are not committed to this repository.** They are AWS's, and their use
is governed by AWS's own terms (see the licence note at the bottom). To run the
scripts, download the package yourself:

1. Download the asset package from <https://aws.amazon.com/architecture/icons/>.
2. Extract it so the four folders below sit directly in this directory.
3. The scripts expect the folder names to end in `_07312026`, the package version
   used here. If you download a newer package, update the paths at the top of
   `diagrams/build_architecture.py` (and the icon file names if AWS renamed any).

Everything in this directory except this README is ignored by git.

## Layout

```
Architecture-Service-Icons_07312026/   One icon per AWS service, grouped by category
  Arch_<Category>/{16,32,48,64}/
    Arch_<Service-Name>_<size>.svg
    Arch_<Service-Name>_<size>.png
    Arch_<Service-Name>_64@5x.png      High-resolution raster (64 only)
Architecture-Group-Icons_07312026/     Group boxes: AWS Cloud, Region, VPC, subnets, and so on
Category-Icons_07312026/               One icon per service category
Resource-Icons_07312026/               Resource-level icons (a bucket, an instance, a rule)
```

About 4,000 files, 13 MB. macOS metadata files were left out.

## Which set to use

| Drawing | Use |
|---|---|
| A service node (ECS, RDS, ALB, S3) | `Architecture-Service-Icons`, the `64` SVG |
| A container for other things (VPC, subnet, Region, Auto Scaling group) | `Architecture-Group-Icons`, the `32` SVG |
| A specific resource inside a service (a bucket, a task, a rule) | `Resource-Icons` |
| A heading or legend by category | `Category-Icons` |

Prefer SVG. Use the `64@5x` PNG only where a raster is required.

## Finding an icon

Names follow the service's official name, with hyphens. Search by name rather
than by folder:

```bash
find assets/aws-icons -name "*Fargate*_64.svg"
```

Icons used by this project (all `64` SVG under `Architecture-Service-Icons_07312026`):

| Service | Path |
|---|---|
| Fargate | `Arch_Containers/64/Arch_AWS-Fargate_64.svg` |
| ECR | `Arch_Containers/64/Arch_Amazon-Elastic-Container-Registry_64.svg` |
| RDS | `Arch_Databases/64/Arch_Amazon-RDS_64.svg` |
| Elastic Load Balancing | `Arch_Networking-Content-Delivery/64/Arch_Elastic-Load-Balancing_64.svg` |
| Route 53 | `Arch_Networking-Content-Delivery/64/Arch_Amazon-Route-53_64.svg` |
| S3 | `Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg` |
| Secrets Manager | `Arch_Security-Identity/64/Arch_AWS-Secrets-Manager_64.svg` |
| CloudWatch | `Arch_Management-Tools/64/Arch_Amazon-CloudWatch_64.svg` |
| SNS | `Arch_Application-Integration/64/Arch_Amazon-Simple-Notification-Service_64.svg` |

## Rules for using them

- Do not recolour, crop, stretch, rotate or redraw an icon. AWS's icon
  guidelines ask for them to be used as supplied; check the current guidelines
  at <https://aws.amazon.com/architecture/icons/>.
- Keep the label next to the icon. An icon without its service name is not a
  diagram.
- Do not use an icon to imply an AWS service is part of the design when it is
  not. This project is a prototype and the diagrams say so.

## Licence note

The icon package is published by AWS and carries no licence file. Its use is
governed by AWS's own terms for the icons, not by this repository's licence.
Redistributing the whole package in a public repository may not be covered by
those terms, so this repository does not include it: the folder is git-ignored
and each contributor downloads the package from the page above. Check AWS's
current terms there before using the icons anywhere else.

The SVG diagrams in `docs/img/` embed some of these icons. They are meant to
illustrate an architecture, which is the purpose AWS publishes the icons for.
