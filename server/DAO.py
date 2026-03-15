from datetime import datetime, timedelta
from uuid import uuid4


class DAO:
    def __init__(self, db=None, dao_id=None, members=None, min_votes=2, approval_ratio=0.5, voting_deadline_hours=24):
        self.db = db
        self.daoID = dao_id or str(uuid4())
        self.members = set(members or [])
        self.proposals = {}
        self.minVotes = int(min_votes)
        self.approvalRatio = float(approval_ratio)
        self.votingDeadline = int(voting_deadline_hours)
        self.executedProposals = set()

    def createProposal(self, eventType, description, bookingID, transactionData, proposer):
        self.validateProposal(eventType, description, bookingID, transactionData, proposer)
        proposal_id = str(uuid4())
        deadline = datetime.utcnow() + timedelta(hours=self.votingDeadline)
        proposal = {
            "proposal_id": proposal_id,
            "event_type": eventType,
            "description": description,
            "booking_id": bookingID,
            "transaction_data": transactionData,
            "proposer": proposer,
            "votes_for": set(),
            "votes_against": set(),
            "status": "PENDING",
            "created_at": datetime.utcnow(),
            "deadline": deadline,
        }
        self.proposals[proposal_id] = proposal
        return proposal

    def voteOnProposal(self, proposalID, memberID, vote):
        proposal = self.proposals[proposalID]
        if memberID not in self.members:
            raise ValueError("Member is not allowed to vote")
        if self.isVotingExpired(proposalID):
            proposal["status"] = "EXPIRED"
            raise ValueError("Voting deadline has passed")
        if self.hasVoted(proposalID, memberID):
            raise ValueError("Member has already voted on this proposal")

        normalized_vote = str(vote).upper()
        if normalized_vote in {"APPROVE", "YES", "TRUE"}:
            proposal["votes_for"].add(memberID)
        elif normalized_vote in {"REJECT", "NO", "FALSE"}:
            proposal["votes_against"].add(memberID)
        else:
            raise ValueError("Vote must be APPROVE or REJECT")

        proposal["status"] = self.checkProposalStatus(proposalID)
        return proposal["status"]

    def hasVoted(self, proposalID, memberID):
        proposal = self.proposals[proposalID]
        return memberID in proposal["votes_for"] or memberID in proposal["votes_against"]

    def countVotes(self, proposalID):
        proposal = self.proposals[proposalID]
        total_votes = len(proposal["votes_for"]) + len(proposal["votes_against"])
        approve_votes = len(proposal["votes_for"])
        reject_votes = len(proposal["votes_against"])
        approval_rate = approve_votes / total_votes if total_votes else 0.0
        return {
            "total_votes": total_votes,
            "approve_votes": approve_votes,
            "reject_votes": reject_votes,
            "approval_rate": approval_rate,
        }

    def checkProposalStatus(self, proposalID):
        proposal = self.proposals[proposalID]
        if proposal["status"] == "EXECUTED":
            return "EXECUTED"
        if proposal["status"] == "CANCELLED":
            return "CANCELLED"
        if self.isApproved(proposalID):
            proposal["status"] = "APPROVED"
        elif self.isRejected(proposalID):
            proposal["status"] = "REJECTED"
        elif self.isVotingExpired(proposalID):
            proposal["status"] = "EXPIRED"
        else:
            proposal["status"] = "PENDING"
        return proposal["status"]

    def isApproved(self, proposalID):
        vote_summary = self.countVotes(proposalID)
        return (
            vote_summary["total_votes"] >= self.minVotes
            and vote_summary["approval_rate"] >= self.approvalRatio
        )

    def isRejected(self, proposalID):
        vote_summary = self.countVotes(proposalID)
        if vote_summary["total_votes"] < self.minVotes:
            return False
        reject_rate = vote_summary["reject_votes"] / vote_summary["total_votes"]
        return reject_rate > (1 - self.approvalRatio)

    def isVotingExpired(self, proposalID):
        proposal = self.proposals[proposalID]
        return datetime.utcnow() > proposal["deadline"]

    def executeProposal(self, proposalID, executor=None):
        proposal = self.proposals[proposalID]
        status = self.checkProposalStatus(proposalID)
        if status != "APPROVED":
            raise ValueError("Proposal must be approved before execution")
        if proposalID in self.executedProposals:
            raise ValueError("Proposal has already been executed")

        execution_result = proposal["transaction_data"]
        if callable(executor):
            execution_result = executor(proposal)

        proposal["status"] = "EXECUTED"
        proposal["execution_result"] = execution_result
        self.executedProposals.add(proposalID)
        return execution_result

    def cancelProposal(self, proposalID):
        proposal = self.proposals[proposalID]
        if proposal["status"] == "EXECUTED":
            raise ValueError("Cannot cancel an executed proposal")
        proposal["status"] = "CANCELLED"
        return proposal

    def getProposalStatus(self, proposalID):
        return self.checkProposalStatus(proposalID)

    def getProposalByBookingID(self, bookingID):
        return [proposal for proposal in self.proposals.values() if proposal["booking_id"] == bookingID]

    def addMember(self, memberID):
        self.members.add(memberID)
        return memberID

    def removeMember(self, memberID):
        self.members.discard(memberID)
        return memberID

    def validateProposal(self, eventType, description, bookingID, transactionData, proposer):
        if proposer not in self.members:
            raise ValueError("Proposer must be a DAO member")
        if not eventType or not description:
            raise ValueError("Proposal event type and description are required")
        if bookingID is None:
            raise ValueError("Booking ID is required")
        if transactionData is None:
            raise ValueError("Transaction data is required")
        return True