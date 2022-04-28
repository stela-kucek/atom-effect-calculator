# Parallel and Distributed Atom-Effect Calculator for a 3D Cartesian Grid

This project demonstrates a simple use case well-suited for parallel and distributed processing. The application was designed in the scope of an assignment for a cloud computing course, and thus makes use of [AWS (Amazon Web Services)](https://aws.amazon.com/) components. Of course, as this was the first encounter with AWS, the solution architecture is suboptimal. However, it can serve as a usage demonstration of AWS's API for Python, and how communication can be achieved among applications running on the AWS infrastructure. If you are interested in the project, read on. 🙂

## Application Description
The designed application is a parallel and distributed atom-effect calculator within a 3D Cartesian grid, which calculates the physical effect of all atoms present in the grid space on the grid points:
![image](https://user-images.githubusercontent.com/18488581/165827456-7125e720-24de-4cef-9996-7ce206b03575.png)

<p align="center"> Figure 1 Example 3d grid (4x4x4 cuboid) </p>

Each atom consists of 4 elements: [x, y, z] coordinates and an energy value. 

The physical effect of an atom on a grid point is calculated by summing up the following values calculated per atom: 

`<energy of atom>/<distance between grid point and atom>`.

The application requires an input from the user specifying the grid size; in this case, the shape of the 3d grid is assumed to be a cube, meaning the lengths of all grid edges are identical (e.g., a grid with grid size 4 would be a 4x4x4 cube, as depicted in Figure 1). 

The user also specifies the number of atoms within the grid.

The application generates the specified number of atoms with randomized values for both their coordinates, and their effect values, then calculates the physical effects of these atoms on all grid points in the given grid, determines the minimal value and returns this minimum along with the grid point with this minimal physical effect.

The application displays the progress of the calculation so that each step in the progress bar is an indication that a grid point was processed.

The application consists of 3 components:
1.	A server providing a GUI for progress visualization (e.g., for how many atoms has the effect been calculated so far) and interaction with the user
2.	An atom-data generator, which will initialize the app with a set of atoms and their corresponding value tuples 
3.	A calculator, whose multiple instances calculate the effects for each atom in parallel

The services communicate using Amazon’s SQS and SNS. Details on the architectural setup are given in the next section. 

## Application Architecture

In this section, an overview and brief description of the application architecture is given. Please note that this is just an overview showing the main components and their high-level interactions (see Figure 2), and that the parallelization and communication details are omitted. 

The application’s central (computing) components are three EC2 instances on which the aforementioned three services are running. 

The services utilize two AWS messaging services to communicate: SNS and SQS. Both SNS and SQS use the FIFO (first in first out) ordering/processing mechanism, which in this case simply allows the user request that came in first to also be processed first. 

In essence, the GUI service creates SNS topics which allow “labeling” of data flows based on the user request, and it subscribes an SQS queue to this topic. As portions of the data are processed, intermediate updates from the GridSolver are pushed in form of notifications to the defined topic. In the meantime, the GUI service polls on the subscribed queue for notification messages and displays the progress via progress bar. 

The GUI service and the AtomGenerator service store relevant data (i.e., grid size, generated atom value tuples and result) to objects in an S3 bucket, which represents the data storage mechanism in this architecture.

![image](https://user-images.githubusercontent.com/18488581/165830447-35ef398e-6431-4ab2-8177-bccec16c4943.png)

<p align="center"> Figure 2 Overall application architecture </p>


